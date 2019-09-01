import boto3
ec2 = boto3.client('ec2')
elb = boto3.client('elbv2')
asg = boto3.client('autoscaling')
ec2res = boto3.resource('ec2')
acm = boto3.client('acm')
from datetime import datetime
import time

####### CHANGE IMAGE ID IF YOU WANT, MINE IS PUBLIC
imageid = 'ami-056ec73517099e4fa'
####### CHANGE IMAGE ID IF YOU WANT, MINE IS PUBLIC

####### CHANGE REGION
regionid = "eu-central-1"
####### CHANGE REGION

now = datetime.now()
dt_string = now.strftime("%d%m%Y%H%M%S")

# input the number of web servers
app_server_number = ''
app_server_number_int = 0


while 1:
    app_server_number = input ("Enter the number of web servers: ")
    try:
        app_server_number_int = int(app_server_number)
        correct = 1
        break
    except ValueError:
        print("That's not an int!")

# create VPC
print("Creating VPC...")
vpc_response = ec2.create_vpc(CidrBlock='172.27.0.0/16')
vpc = ec2res.Vpc(vpc_response["Vpc"]["VpcId"])

# enable public dns hostname 
ec2.modify_vpc_attribute( VpcId = vpc.id , EnableDnsSupport = { 'Value': True } )
ec2.modify_vpc_attribute( VpcId = vpc.id , EnableDnsHostnames = { 'Value': True } )

# create an internet gateway and attach it to VPC
print("Creating InternetGateway...")
internetgateway_response = ec2.create_internet_gateway()
internetgateway = ec2res.InternetGateway(internetgateway_response["InternetGateway"]["InternetGatewayId"])
vpc.attach_internet_gateway(InternetGatewayId=internetgateway.id)

# modify the route table to work with the internet gateway
print("Modifying Route Table...")
for route_table in vpc.route_tables.all():  
    route_table.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=internetgateway.id
)

# create subnets and associate it with route table
print("Creating Subnets...")
subnet1 = vpc.create_subnet(CidrBlock='172.27.0.0/20', AvailabilityZone="{}{}".format(regionid, "a"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet1.id
)
subnet2 = vpc.create_subnet(CidrBlock='172.27.16.0/20', AvailabilityZone="{}{}".format(regionid, "b"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet2.id
)
subnet3 = vpc.create_subnet(CidrBlock='172.27.32.0/20', AvailabilityZone="{}{}".format(regionid, "c"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet3.id
)

# create a security group and allow SSH inbound rule through the VPC
print("Creating Security Group...")
sgname = 'sg' + dt_string
securitygroup_response = ec2.create_security_group(GroupName=sgname, Description='test', VpcId=vpc.id)
securitygroup = ec2res.SecurityGroup(securitygroup_response["GroupId"])
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=22, ToPort=22)
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=80, ToPort=80)
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=443, ToPort=443)

# create Key Pair
print("Creating Key Pair...")
kname = 'k' + dt_string
kfile = kname + ".pem"
print("SSH Private Key File Name: " + kfile)

response = ec2.create_key_pair(KeyName=kname)

keyfile = open(kfile,"w+")
keyfile.write(response['KeyMaterial'])
keyfile.close()

# import certificate to acm
print("Importing ACM Certificate...")
pubkey = ''
prikey = ''

with open ("my-cert-key.pem", "r") as myfile:
    pubkey=myfile.readlines()

work_pubkey = ' '.join(pubkey)

with open ("my-private-key.pem", "r") as myfile:
    prikey=myfile.readlines()

work_prikey = ' '.join(prikey)

response = acm.import_certificate(
    Certificate=work_pubkey,
    PrivateKey=work_prikey
)

certarn=response['CertificateArn']

ltname = 'lt' + dt_string
tgname = 'tg' + dt_string
agsname = 'ags' + dt_string
albname = 'alb' + dt_string

# create launch template for the autoscaling group 
print("Creating Launch Templates...")
lt = ec2.create_launch_template(
    LaunchTemplateName=ltname,
    LaunchTemplateData={
        'ImageId': imageid, # the image is a public image I made, can be changed
        'InstanceType': 't2.micro',
        'KeyName': kname,
        'SecurityGroupIds': [
            securitygroup.id,
        ]
    }
)

# create target group for the load balancer
print("Creating Target Group...")
response = elb.create_target_group(
    Name=tgname,
    Port=80,
    Protocol='HTTP',
    VpcId=vpc.id
)

tgarn = response['TargetGroups'][0]['TargetGroupArn']

# create autoscaling group
print("Creating AutoScaling Group...")
vpczone = subnet1.id + ', ' + subnet2.id +  ', ' + subnet3.id

response = asg.create_auto_scaling_group(
    AutoScalingGroupName=agsname,
    LaunchTemplate={
        'LaunchTemplateName': ltname,
    },
    MaxSize=app_server_number_int,
    MinSize=app_server_number_int,
    VPCZoneIdentifier=vpczone,
    HealthCheckGracePeriod=150
)

# create application load balancer
print("Creating Application Load Balancer...")
response = elb.create_load_balancer(
    Name=albname,
    SecurityGroups=[
        securitygroup.id,
    ],
    Type='application',
    Subnets=[
        subnet1.id,
        subnet2.id,
        subnet3.id
    ],
)

lbarn = response['LoadBalancers'][0]['LoadBalancerArn']
dns = response['LoadBalancers'][0]['DNSName']

# attach http/https listerners to load balancer
print("Attaching listeners to Load Balancer...")
response = elb.create_listener(
    Certificates=[
        {
            'CertificateArn': certarn,
        },
    ],
    DefaultActions=[
        {
            'TargetGroupArn': tgarn,
            'Type': 'forward',
        },
    ],
    LoadBalancerArn=lbarn,
    Port=443,
    Protocol='HTTPS',
    SslPolicy='ELBSecurityPolicy-2016-08',
)

response = elb.create_listener(
    DefaultActions=[
        {
            'TargetGroupArn': tgarn,
            'Type': 'forward',
        },
    ],
    LoadBalancerArn=lbarn,
    Port=80,
    Protocol='HTTP'
)

# attach target group to auto scaling group
print("Attaching Target Group to AutoScaling Group...")
response = asg.attach_load_balancer_target_groups(
    AutoScalingGroupName=agsname,
    TargetGroupARNs=[
        tgarn,
    ]
)

# checks if the targets in the target group are healthy
all_healthy = 0

while 1:
    all_healthy = 0
    response = elb.describe_target_health(
        TargetGroupArn=tgarn,
    )
    for target in response['TargetHealthDescriptions']:
        if target['TargetHealth']['State'] == 'healthy':
            all_healthy = all_healthy + 1
    if all_healthy == 3:
        break
    print("Checking if Targets are healthy...")
    time.sleep(15)

print("Everything is ready!")
print("The DNS is:")
print(dns)
print("You can access it in either HTTP or HTTPS")