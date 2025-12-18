import boto3
from botocore.exceptions import ClientError
from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
import os

class EC2Manager:
    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.ec2 = self.session.resource('ec2')
        self.client = self.session.client('ec2')
        self.instances_to_ignore = self._load_ignored_instances()
    
    def _load_ignored_instances(self):
        ignored = os.getenv('INSTANCES_TO_IGNORE', '')
        if ignored:
            return [instance_id.strip() for instance_id in ignored.split(',') if instance_id.strip()]
        return []
    
    def _should_ignore_instance(self, instance_id):
        return instance_id in self.instances_to_ignore

    def get_all_instances(self):
        instances = []
        response = self.client.describe_instances()
        
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                
                if state == 'terminated':
                    continue
                
                instance_name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), '')
                if not instance_name:
                    continue
                
                if not self._should_ignore_instance(instance_id):
                    instances.append({
                        'id': instance_id,
                        'state': state,
                        'name': instance_name
                    })
        
        return instances

    def start_instance(self, instance_id):
        if self._should_ignore_instance(instance_id):
            return False, ""
        
        try:
            instance = self.ec2.Instance(instance_id)
            instance.load()
            
            if instance.state['Name'] == 'running':
                return False, f"⚠️ Instance {instance_id} is already running"
            
            instance.start()
            return True, f"⏳ Starting instance {instance_id}"
        except ClientError as e:
            return False, str(e)

    def stop_instance(self, instance_id):
        if self._should_ignore_instance(instance_id):
            return False, ""
        
        try:
            instance = self.ec2.Instance(instance_id)
            instance.load()
            
            if instance.state['Name'] == 'stopped':
                return False, f"⚠️ Instance {instance_id} is already stopped"
            
            instance.stop()
            return True, f"⏳ Stopping Instance {instance_id}"
        except ClientError as e:
            return False, str(e)

    def start_all_instances(self):
        instances = self.get_all_instances()
        results = []
        
        for instance in instances:
            if instance['state'] == 'stopped':
                success, message = self.start_instance(instance['id'])
                if message:
                    results.append(f"{instance['id']}: {message}")
            elif instance['state'] == 'running':
                results.append(f"⚠️ {instance['id']}: Instance is already running")
        
        return results

    def stop_all_instances(self):
        instances = self.get_all_instances()
        results = []
        
        for instance in instances:
            if instance['state'] == 'running':
                success, message = self.stop_instance(instance['id'])
                if message:
                    results.append(f"{instance['id']}: {message}")
            elif instance['state'] == 'stopped':
                results.append(f"⚠️ {instance['id']}: Instance is already stopped")
        
        return results