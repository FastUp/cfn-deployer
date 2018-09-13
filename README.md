# CloudFormation Deployer

AWS CLI provides a well documented command to create and manage CloudFormation Stacks. That command may become tedious 
or error prone when frequent change sets are needed or when change management is shared in a team. 
This tool simplifies creating, managing and sharing Cloudformation stacks on a command line.


## Why use it
CFN Deployer applies a convention to creating and managing Cloudformation stacks. 
Instead of creating a command line with the right command, right options each time, one may setup a "project" 
configuration and run the CFN Deployer. 
This project configuration can be committed to a Version Control system such as git or svn and shared among team members. 
This provides a repeatable, standard way to create and manage cloudformation stacks from the command line.

## How to use it
CFN Deployer looks for a project configuration file at the file specified by the --config parameter. In that project 
config file, it looks for a series of yaml keys and values. Here is a minimum required project configuration example 
with hints of its use:

```yaml
### The project_name is used to create the cloudformation stack's name. In this case, the name of the resulting 
cloudformation stack will be "MyCloudformationStack" 
project_name: MyCloudformationStack 
### CFN Deployer looks for a template at the provided path to create the stack from.
template: /path/to/mycloudformationtemplate.yaml
```

Here is a fully fleshed project configuration file example.
```yaml
### The change_set_number is an automatically generated serial number for creating changesets[1] in CloudFormation. 
change_set_number: 29
### Here, in Create Arguments, one may provide arguments supported by cloudformation boto3[2][3] with exceptions. 
### Exceptions are: StackName, TemplateBody, TemplateURL, Parameters, Capabilities. These keys will be ignored.
create_arguments:
  ### An optional role ARN that Cloudformation[4] assumes to create the stack
  RoleARN: arn:aws:iam::1234567890:role/MyCloudformationRole
### Optional: The AWS credential profile[4] to use in the user's workstation where this command is being run. 
### Default is to use the default profile.
credential_profile: fastupappprod
### The project_name is used to create the cloudformation stack's name. In this case, the name of the resulting 
project_name: FastUpIAMAccess
### This optional key overrides the user's workstation AWS CLI configuration[5] 
region: us-east-1
### CFN Deployer looks for a template[6] at the provided path to create the stack from.
template: /path/to/mycloudformationtemplate.yaml
### The template parameters[7] defined and required in the cloudformation template. 
### This file should be in a format that boto3 expects[7].
template_parameters: /path/to/mycloudformationtemplate.yaml
### The version can be any string and will be appended to project_name to form the Cloudformation stack name. 
version: 1.0.0
### The env is an environment name that will be appended to project_name to form the Cloudformation stack name.
env: prod
### Release Bucket is required for Packaging Lambda functions. The deployer packages lambda function code and uploads 
### to this bucket for subsequent command to deploy it.
### Please Note: CFN Deployer does not work with SAM templates yet, because there is no boto3 API equivalent for the 
### CLI command "aws cloudformation package"[]
release_bucket: myLambdaDeployerBucket
### Lambda Code is a structure to specify lambda code location. Except for the folder property, this is automatically modified by the deployer. 
lambda_code: 
    ### Folder is the local folder name that contains the function. Required.
    folder: /path/to/lambda/code
    ### The parameter name inside the template that specifies the S3 Bucket for the uploaded Lambda package
    ### Automatically modified by the deployer.
    s3_bucket_param_name: MyLambdaS3BucketNameParam
    ### The parameter name inside the template that specifies the s3 version of the uploaded Lambda package. 
    ### Automatically modified by the deployer.
    s3_version_param_name: MyLambdaS3VersionParam
    ### The S3 key where the code lives.
    ### Automatically modified by the deployer.
    s3_key_param_name: /lambda_packages/MyLambda/MyLambda.zip

```


## Install instructions

To install the [latest release](https://github.com/FastUp/cfn-deployer/releases/latest) from the master branch:
`
  pip install git+https://github.com/FastUp/cfn-deployer.git@Alpha
`
## Usage
To view help: 
`deployer help`

### To create stack:
`deployer create`
#### Example
```
deloyer --config mystack.project.yaml create
```

### To create a change-set on a stack:
`deployer change`
#### Example
```
deloyer --config mystack.project.yaml change
```


### To execute a change-set:
`deployer exec-change`
#### Example
```
deloyer --config mystack.project.yaml exec-change --change-set-name ChangeSet-29
```

### To delete a stack:
`deployer delete`
### Example
```
deloyer --config mystack.project.yaml delete
```

### To package a Lambda function:
`deployer package`
### Example
```
deloyer --config mystack.project.yaml package
```

To estimate costs:
`deployer cost`

