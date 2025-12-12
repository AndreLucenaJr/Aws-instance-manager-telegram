import boto3
from botocore.exceptions import ClientError
from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION

class EC2Manager:
    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.ec2 = self.session.resource('ec2')
        self.client = self.session.client('ec2')

    def get_all_instances(self):
        instances = []
        response = self.client.describe_instances()
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append({
                    'id': instance['InstanceId'],
                    'state': instance['State']['Name'],
                    'name': next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'No Name')
                })
        
        return instances

    def start_instance(self, instance_id):
        try:
            instance = self.ec2.Instance(instance_id)
            instance.load()
            
            if instance.state['Name'] == 'running':
                return False, f"⚠️ Instância {instance_id} já está iniciada"
            
            instance.start()
            return True, f"⏳ Iniciando instância {instance_id}"
        except ClientError as e:
            return False, str(e)

    def stop_instance(self, instance_id):
        try:
            instance = self.ec2.Instance(instance_id)
            instance.load()
            
            if instance.state['Name'] == 'stopped':
                return False, f"⚠️ Instância {instance_id} já está parada"
            
            instance.stop()
            return True, f"⏳ Parando instância {instance_id}"
        except ClientError as e:
            return False, str(e)

    def start_all_instances(self):
        instances = self.get_all_instances()
        results = []
        
        for instance in instances:
            if instance['state'] == 'stopped':
                success, message = self.start_instance(instance['id'])
                results.append(f"{instance['id']}: {message}")
            elif instance['state'] == 'running':
                results.append(f"⚠️ {instance['id']}: Instância já está iniciada")
        
        return results

    def stop_all_instances(self):
        instances = self.get_all_instances()
        results = []
        
        for instance in instances:
            if instance['state'] == 'running':
                success, message = self.stop_instance(instance['id'])
                results.append(f"{instance['id']}: {message}")
            elif instance['state'] == 'stopped':
                results.append(f"⚠️ {instance['id']}: Instância já está parada")
        
        return results