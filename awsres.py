import boto3
ec2 = boto3.client('ec2')
elb = boto3.client('elbv2')
asg = boto3.client('autoscaling')
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

ltname = 'lt' + dt_string
tgname = 'tg' + dt_string
agsname = 'ags' + dt_string
albname = 'alb' + dt_string

lt = ec2.create_launch_template(
    LaunchTemplateName=ltname,
    LaunchTemplateData={
        'ImageId': 'ami-056ec73517099e4fa',
        'InstanceType': 't2.micro',
        'KeyName': 'def_key',
        'SecurityGroupIds': [
            'sg-08cab05c0efaeadcb',
        ]
    }
)

response = elb.create_target_group(
    Name=tgname,
    Port=80,
    Protocol='HTTP',
    VpcId='vpc-c6fa11ac'
)

tgarn = response['TargetGroups'][0]['TargetGroupArn']

response = asg.create_auto_scaling_group(
    AutoScalingGroupName=agsname,
    LaunchTemplate={
        'LaunchTemplateName': ltname,
    },
    MaxSize=app_server_number_int,
    MinSize=app_server_number_int,
    AvailabilityZones=[
        'eu-central-1a',
        'eu-central-1b',
        'eu-central-1c'
    ],
    HealthCheckGracePeriod=150
)

response = elb.create_load_balancer(
    Name=albname,
    SecurityGroups=[
        'sg-08cab05c0efaeadcb',
    ],
    Type='application',
    Subnets=[
        'subnet-5ba9b416',
        'subnet-b63ae9dc',
        'subnet-21474e5c'
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