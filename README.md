# CloudFormation Deployer

Deploying cloudformation stacks to AWS from the command line is fairly easy. It may become tedious or a bit error prone when frequent change sets are needed. This tool simplifies the creation and updates to a CloudFormation stack.


## Install instructions

To install the [latest release](https://github.com/FastUp/cfn-deployer/releases/latest) from the master branch:
`
  pip install git+https://github.com/FastUp/cfn-deployer.git@GA
`
## Usage
To view help: 
`deployer help`

To create stack:
`deployer create`

To create a change-set on a stack:
`deployer change`

To execute a change-set:
`deployer exec-change`

To delete a stack:
`deployer delete`

To package a Lambda function:
`deployer package`

To estimate costs:
`deployer cost`


### Folder setup
This tool requires that cloudformation templates be kept under a folder named `cloudformation` and lambda code be kept in subfolders under a folder named `lambda`
