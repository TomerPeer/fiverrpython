# fiverrpython

Prerequisites - 

1. install python 3 (python 3.7 recommended)
2. install aws cli tools, boto3 and datetime with pip
3. configure aws cli with your aws account
4. run and enjoy :)

files in project:
awsres.py - the python code for provisioning
my-cert-key.pem - certificate body from openssl
my-private-key.pem - certificate private key from openssl

notes:

* The program creates it's own VPC in CIDR 172.27.0.0/16, so dont peer it into VPCs with an overlaping CIDR.
* The Secutiry group is created in the program and attached to the VPC.
* The SSH Key-pair is generated in the program thorugh AWS EC2 Key-Pair Service. The public key is attached to the EC2 instances. The private key is generated in the folder where the program is executed with the name k<datetime>.
* The SSL certificate is pregenerated and PEM coded. It is provided within the repository. You can generate your own with openssl or with AWS ACM.
* The parametes imageid holds the image that the auto scaling group creates. You can create your own image and use it.