import boto3
ec2 = boto3.client('ec2')
elb = boto3.client('elbv2')
asg = boto3.client('autoscaling')
ec2res = boto3.resource('ec2')
from datetime import datetime

now = datetime.now()
dt_string = now.strftime("%d%m%Y%H%M%S")

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
vpc_response = ec2.create_vpc(CidrBlock='172.27.0.0/16')
vpc = ec2res.Vpc(vpc_response["Vpc"]["VpcId"])

# enable public dns hostname so that we can SSH into it later
ec2.modify_vpc_attribute( VpcId = vpc.id , EnableDnsSupport = { 'Value': True } )
ec2.modify_vpc_attribute( VpcId = vpc.id , EnableDnsHostnames = { 'Value': True } )

# create an internet gateway and attach it to VPC
internetgateway_response = ec2.create_internet_gateway()
internetgateway = ec2res.InternetGateway(internetgateway_response["InternetGateway"]["InternetGatewayId"])
vpc.attach_internet_gateway(InternetGatewayId=internetgateway.id)

# create a route table and a public route
for route_table in vpc.route_tables.all():  
    route_table.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=internetgateway.id
)

# create subnet and associate it with route table
subnet1 = vpc.create_subnet(CidrBlock='172.27.0.0/20', AvailabilityZone="{}{}".format("eu-central-", "1a"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet1.id
)
subnet2 = vpc.create_subnet(CidrBlock='172.27.16.0/20', AvailabilityZone="{}{}".format("eu-central-", "1b"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet2.id
)
subnet3 = vpc.create_subnet(CidrBlock='172.27.32.0/20', AvailabilityZone="{}{}".format("eu-central-", "1c"))
resp = ec2.modify_subnet_attribute(
    MapPublicIpOnLaunch={
        'Value': True
    },
    SubnetId=subnet3.id
)
sgname = 'sg' + dt_string
# Create a security group and allow SSH inbound rule through the VPC
securitygroup_response = ec2.create_security_group(GroupName=sgname, Description='test', VpcId=vpc.id)
securitygroup = ec2res.SecurityGroup(securitygroup_response["GroupId"])
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=22, ToPort=22)
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=80, ToPort=80)
securitygroup.authorize_ingress(CidrIp='0.0.0.0/0', IpProtocol='tcp', FromPort=443, ToPort=443)

kname = 'k' + dt_string
kfile = kname + ".pem"

response = ec2.create_key_pair(KeyName=kname)

keyfile = open(kfile,"w+")
keyfile.write(response['KeyMaterial'])
keyfile.close()

ltname = 'lt' + dt_string
tgname = 'tg' + dt_string
agsname = 'ags' + dt_string
albname = 'alb' + dt_string

lt = ec2.create_launch_template(
    LaunchTemplateName=ltname,
    LaunchTemplateData={
        'ImageId': 'ami-056ec73517099e4fa',
        'InstanceType': 't2.micro',
        'KeyName': kname,
        'SecurityGroupIds': [
            securitygroup.id,
        ]
    }
)

response = elb.create_target_group(
    Name=tgname,
    Port=80,
    Protocol='HTTP',
    VpcId=vpc.id
)

tgarn = response['TargetGroups'][0]['TargetGroupArn']
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

response = elb.create_listener(
    Certificates=[
        {
            'CertificateArn': 'arn:aws:iam::654932425973:server-certificate/MyCert',
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

response = asg.attach_load_balancer_target_groups(
    AutoScalingGroupName=agsname,
    TargetGroupARNs=[
        tgarn,
    ]
)

print(dns)