from __future__ import print_function

import argparse
import hashlib
import imp
import json
import os.path
import platform
import sys
import zipfile

import boto3
import os
import yaml
from botocore.exceptions import ClientError
from ruamel import yaml as ry


class Ref(str):
    @staticmethod
    def yaml_dumper(dumper, data):
        return dumper.represent_scalar('!Ref', u'{}'.format(data), style='x')

    @staticmethod
    def yaml_constructor(loader, node):
        value = loader.construct_scalar(node)
        return Ref(value)


ry.add_representer(Ref, Ref.yaml_dumper)
ry.add_constructor('!Ref', Ref.yaml_constructor,
                   constructor=ry.constructor.SafeConstructor)


def choose_scalar_style(self):
    if self.event.style == 'x':
        return ''
    return self.org_choose_scalar_style()


ry.emitter.Emitter.org_choose_scalar_style = ry.emitter.Emitter.choose_scalar_style
ry.emitter.Emitter.choose_scalar_style = choose_scalar_style

tmp_folder = 'C:\\temp\\' if platform.system() == 'Windows' else "/tmp/"

boto3_session = None


def _zip_dir(path, a_zip_file):
    for root, dirs, files in os.walk(path):
        for a_file in files:
            a_zip_file.write(os.path.join(root, a_file))
    a_zip_file.close()


def release_lambda(config, each_lambda_config):
    lambda_folder = each_lambda_config["folder"]
    release_bucket = config["release_bucket"]
    os.chdir('lambda' + "/" + lambda_folder)
    code_zip_file_name = lambda_folder + '.zip'
    zip_it_in_tmp(code_zip_file_name)
    lambda_code_zip_key = checked_upload(tmp_folder, code_zip_file_name, config, "lambda")
    os.chdir('../..')
    modify_template(
        config, each_lambda_config,
        lambda_code_zip_key,
        release_bucket,
        outer_key="Code",
        bucket="S3Bucket",
        key="S3Key"
    )


def modify_template(config, each_lambda_config, upload_s3_key, release_bucket, **kwargs):
    with open("cloudformation/" + config["template_parameters"], mode="r+") as template_config_file:
        template_config = json.load(template_config_file)
        bucket_param_config = None
        code_key_param = None
        for each_config in template_config:
            if each_config["ParameterKey"] == each_lambda_config["code_s3_bucket_param_name"]:
                bucket_param_config = each_config
            if each_config["ParameterKey"] == each_lambda_config["code_s3_key_param_name"]:
                code_key_param = each_config
        if bucket_param_config == None:
            bucket_param_config = {}
            template_config.append(bucket_param_config)
        if code_key_param == None:
            code_key_param = {}
            template_config.append(code_key_param)
        bucket_param_config["ParameterKey"] = each_lambda_config["code_s3_bucket_param_name"]
        bucket_param_config["ParameterValue"] = release_bucket
        code_key_param["ParameterKey"] = each_lambda_config["code_s3_key_param_name"]
        code_key_param["ParameterValue"] = upload_s3_key
        template_config_file.seek(0)
        json.dump(template_config, template_config_file, indent=2)
        template_config_file.truncate()

    with open("cloudformation/" + config["template"], mode="r+") as template_file:
        template_contents = json.load(template_file)
        template_contents["Resources"][each_lambda_config["logical_resource_name"]]["Properties"][kwargs["outer_key"]] = {
            kwargs["bucket"]: release_bucket,
            kwargs["key"]: upload_s3_key
        }
        # template_contents["Resources"][each_lambda_config["function_version_logical_resource_name"]]["Properties"]["CodeSha256"] = new_hash
        template_file.seek(0)
        json.dump(template_contents, template_file, indent=2)
        template_file.truncate()


def checked_upload(directory, file_name, config, s3_prefix):
    release_bucket = config["release_bucket"]
    version = config["version"]
    project_name = config["project_name"]
    env = config["env"]
    new_hash = calculate_hash(directory + file_name)
    s3_client = boto3_session.resource('s3')
    object_s3_key = project_name + "/" + version + "/" + env + '/' + s3_prefix + '/' + file_name
    hash_s3_key = project_name + "/" + version + "/" + env + '/' + s3_prefix + '/' + file_name + ".md5"
    hash_s3_obj = s3_client.Object(release_bucket, hash_s3_key)
    deployed_hash = None
    try:
        deployed_hash = hash_s3_obj.get()["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(
                "MD5 hashcode of file " + directory + file_name + " was never uploaded or has been deleted. " +
                "Will upload new MD5 hashcode "
                + new_hash
            )
        else:
            raise e
    if deployed_hash is None or deployed_hash != new_hash:
        print(
            "MD5 hashcode of deployed lambda code in folder " + directory + file_name + "(" + str(deployed_hash) +
            ") is not same as MD5 hashcode of new code (" + new_hash +
            "). Will upload new code."
        )
        print("\ts3://" + release_bucket + "/" + hash_s3_key)
        hash_s3_obj.put(Body=bytes(new_hash))
        lambda_code_s3_obj = s3_client.Object(release_bucket, object_s3_key)
        print("\ts3://" + release_bucket + "/" + object_s3_key)
        lambda_code_s3_obj.upload_file(directory + file_name)

    else:
        print(
            "MD5 hashcode of deployed lambda code in folder " + directory + file_name + " (" + deployed_hash +
            ") is same as MD5 hashcode of new code " + new_hash +
            ". Will not upload new code."
        )
    return object_s3_key


def zip_it_in_tmp(file_name):
    lambda_code_zip = zipfile.ZipFile(tmp_folder + file_name, 'w')
    _zip_dir(".", lambda_code_zip)


def calculate_hash(filename):
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    with open(filename, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    new_hash = hasher.hexdigest()
    return new_hash


def release_api_spec(config):
    api_file = config["api_spec"]["file"]
    release_bucket = config["release_bucket"]
    os.chdir('api_spec' + "/")
    upload_s3_key = checked_upload("./", api_file, config, "api")
    os.chdir('..')
    modify_template(
        config,
        config["api_spec"]["logical_resource_name"],
        upload_s3_key,
        release_bucket,
        outer_key="BodyS3Location",
        bucket="Bucket",
        key="Key"
    )


def do_release(config):
    if "lambda_code" in config:
        print("Uploading lambda code: ")
        for each_lambda_folder in config["lambda_code"]:
            release_lambda(
                config,
                each_lambda_folder

            )
    if "api_spec" in config:
        print("Uploading api spec: ")
        release_api_spec(config)


def do_change(config):
    cfn_client = boto3_session.client('cloudformation')
    change_set_num = 0
    if "change_set_number" in config:
        change_set_num = config["change_set_number"]
    change_set_num += 1
    config["change_set_number"] = change_set_num
    with open(args.config, "w") as config_file:
        yaml.dump(config, config_file, default_flow_style=False)
    stack_arguments = make_stack_arguments(config)
    stack_arguments["ChangeSetName"] = "ChangeSet" + "-" + str(config["change_set_number"])
    cfn_client.create_change_set(**stack_arguments)


def make_stack_arguments(config):
    stack_name = create_stack_name(config)
    data = get_template_as_string(config)
    stack_arguments = {
        "StackName": stack_name,
        "TemplateBody": data,
    }
    if "template_parameters" in config:
        stack_arguments["Parameters"] = json.load(
            open(
                "cloudformation/" + config["template_parameters"]
            )
        )
    if args.iam_capabilities is not None:
        stack_arguments["Capabilities"] = [args.iam_capabilities]
    if "create_arguments" in config:
        config["create_arguments"].pop("StackName", None)
        config["create_arguments"].pop("TemplateBody", None)
        config["create_arguments"].pop("TemplateURL", None)
        config["create_arguments"].pop("Parameters", None)
        config["create_arguments"].pop("Capabilities", None)
        stack_arguments.update(config["create_arguments"])
    return stack_arguments


def create_stack_name(config):
    env_suffix = "-" + get_env(config)
    ver_suffix = "-" + get_ver(config).replace(".", "-")
    stack_name = config["project_name"] + ver_suffix + env_suffix
    return stack_name


def print_arguments(create_stack_arguments):
    import copy
    deepcopy = copy.deepcopy(create_stack_arguments)
    deepcopy["TemplateBody"] = "Removed"
    print(deepcopy)


def get_template_as_string(config):
    template_stream = open("cloudformation/" + config["template"])
    data = ""
    lines = template_stream.readlines()
    for line in lines:
        data += line
    return data


def do_create(config):
    if "build_helper" in config:
        helper = imp.load_source("helper", config["build_helper"])
        dynamic_params = helper.create_dynamic_template_parameters(config)

    cfn_client = boto3_session.client('cloudformation')
    stack_arguments = make_stack_arguments(config)
    print_arguments(stack_arguments)
    create_stack_response = cfn_client.create_stack(**stack_arguments)
    print("Create Stack Response : " + json.dumps(create_stack_response))


def do_cost(config):
    cfn_client = boto3_session.client('cloudformation')
    stack_arguments = {
        "TemplateBody": get_template_as_string(config),
    }
    if "template_parameters" in config:
        stack_arguments["Parameters"] = json.load(
            open(
                "cloudformation/" + config["template_parameters"]
            )
        )

    cost = cfn_client.estimate_template_cost(**stack_arguments)
    print(cost)


def do_delete(config):
    stack_name = create_stack_name(config)
    print(
        "This will delete stack " + stack_name + ". "
                                                 "Please confirm by entering the statement without the quotes: "
                                                 "\"Yes, I want to delete this stack.\""
    )
    import sys
    line = sys.stdin.readline().strip()
    if not line == "Yes, I want to delete this stack.":
        print("OK, not deleting.")
        sys.exit(1)
    print("OK, deleting stack " + stack_name)
    cfn_client = boto3_session.client('cloudformation')
    stack_arguments = {"StackName": stack_name}
    if "resources_to_retain" in config:
        stack_arguments.update({"RetainResources": config["resources_to_retain"]})
    cfn_client.delete_stack(**stack_arguments)


args = None


def do_exec_change(config):
    stack_name = create_stack_name(config)
    cfn_client = boto3_session.client('cloudformation')
    method_args = {"ChangeSetName": args.change_set_name, "StackName": stack_name}
    cfn_client.execute_change_set(**method_args)


def do_init():
    if os.path.isfile("project.yaml"):
        print("project.yaml already exists. Cannot create. Exiting.")
        sys.exit(0)
    if not os.path.exists("cloudformation"):
        print("directory named cloudformation does not exist. Creating.")
        os.mkdir("cloudformation")
    if os.path.isfile("cloudformation/template.yaml") or os.path.isfile("cloudformation/template.config.json"):
        print("Either template.yaml or template.config.json already exists. Cannot create. Exiting.")
        sys.exit(0)
    with(open("project.yaml", "w+")) as new_project_file:
        yaml.dump(
            {
                "env": "dev",
                "project_name": "ChangeMe",
                "region": "us-east-1",
                "template": "template.yaml",
                "template_parameters": "template.config.json",
                "version": "1.0.0"
            },
            new_project_file,
            default_flow_style=False
        )
    with(open("cloudformation/template.yaml", "w+")) as new_template:
        ry.dump(
            {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Description": "ChangeMe",
                "Resources": {
                    "AResource": {
                        "Type": "AWS::EC2::Instance",
                        "Properties":
                            {
                                "ImageId": Ref("AParameter")
                            }
                    }

                },
                "Parameters": {
                    "AParameter": {
                        "Type": "String"
                    }
                }
            },
            new_template,
            default_flow_style=False
        )
    with(open("cloudformation/template.config.json", "w+")) as new_template_config:
        json.dump(
            [
                {
                    "ParameterKey": "AParameter",
                    "ParameterValue": "ami-22ce4934"
                }
            ],
            new_template_config,
            indent=4
        )
    pass


def run():
    parse_args()
    current_module = sys.modules[__name__]
    if args.target == "init":
        do_init()
    else:
        try:
            build_config = yaml.load(open(args.config))
            credential_profile = build_config[
                "credential_profile"] if "credential_profile" in build_config else "default"
            if "region" in build_config:
                session_config = {
                    "profile_name": credential_profile,
                    "region_name": build_config["region"]
                }
            else:
                session_config = {
                    "profile_name": credential_profile
                }

            current_module.boto3_session = boto3.session.Session(**session_config)
        except IOError as e:
            print(
                "Cannot continue. Could not open file " + args.config + ". Please ensure it exists and is readable.")
            raise e

        if args.target == "package":
            do_release(build_config)
        elif args.target == "create":
            do_create(build_config)
        elif args.target == "change":
            do_change(build_config)
        elif args.target == "cost":
            do_cost(build_config)
        elif args.target == "delete":
            do_delete(build_config)
        elif args.target == "exec-change":
            do_exec_change(build_config)


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='''
        AWS Deployer
        ============
        Use this to release and deploy cloudformation templates and lambda functions.
        ''')
    parser.add_argument(
        "target",
        choices=["package", "create", "change", "exec-change", "cost", "delete", "init"],
        help='''
        package - zips up lambda code and uploads to S3 under a folder structure reflecting the project
        name, version and environment as configured in config yaml.

        create - creates the cloudformation stack in AWS. The stack name includes the project name, environment and
        version. This will also create all resources in the stack. This does not wait for the stack creation to be
        completed, successful or failed.

        change - creates a change set for an existing stack with the same project name, environment and version.

        cost - estimates cost of the template.

        delete - delete the stack. This is permanent and irreversible.

        init - create a single empty cloudformation template and a configuration file
        
        '''
    )
    parser.add_argument(
        "--config",
        default="project.yaml",
        help='''
        Set this to a file path that contains the build configuration. Defaults to project.yaml in the current dir.
        '''
    )
    parser.add_argument(
        "--iam-capabilities",
        help='''
        Set to iam to acknowledge that the template contains IAM resources. See Cloudformation documentation for valid
        values
        '''
    )
    parser.add_argument(
        "--change-set-name",
        help='''
        If executing a change set, this must be set.
        '''
    )
    current_module = sys.modules[__name__]
    current_module.args = parser.parse_args()
    if args.target == "exec-change" and not hasattr(args, "change_set_name"):
        parser.error("target exec_change must be accompanied by option --change-set-name")
    return args


def get_config_property(config, key, default):
    if key in config:
        return config[key]
    else:
        return default


def get_env(config):
    return get_config_property(config, "env", "")


def get_ver(config):
    return get_config_property(config, "version", "")


if __name__ == "__main__":
    run()
