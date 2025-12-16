import schedule
import time
import threading
from datetime import datetime, timedelta
from aws.ec2_manager import EC2Manager
from database.postgres import get_schedules, delete_schedule, add_schedule
import pytz
from config import TZ_TIMEZONE
ec2_manager = EC2Manager()

class Scheduler:
    def __init__(self):
        self.running = False
        self.thread = None
    
    def execute_scheduled_task(self, schedule_id, instance_id, action, dias_semana, horario):
        if instance_id == 'all':
            if action == 'start':
                ec2_manager.start_all_instances()
            elif action == 'stop':
                ec2_manager.stop_all_instances()
        else:
            if action == 'start':
                ec2_manager.start_instance(instance_id)
            elif action == 'stop':
                ec2_manager.stop_instance(instance_id)
        
        chat_id = None
        for schedule_data in get_schedules():
            if schedule_data['id'] == schedule_id:
                chat_id = schedule_data['chat_id']
                break
        
        if dias_semana and horario and chat_id:
            try:
                dias_lista = [int(d) for d in dias_semana.split(',') if d]
                hora, minuto = map(int, horario.split(':'))
                
                tz = pytz.timezone(TZ_TIMEZONE)
                agora = datetime.now(tz)
                
                for i in range(1, 8):
                    data_futura = agora + timedelta(days=i)
                    if data_futura.weekday() in dias_lista:
                        data_agendamento = datetime.combine(data_futura.date(), time(hora, minuto))
                        data_agendamento = tz.localize(data_agendamento)
                        data_agendamento_utc = data_agendamento.astimezone(pytz.UTC)
                        
                        add_schedule(
                            chat_id=chat_id,
                            instance_id=instance_id,
                            action=action,
                            schedule_time=data_agendamento_utc,
                            dias_semana=dias_semana,
                            horario=horario
                        )
                        break
            except Exception as e:
                print(f"Erro ao recriar agendamento: {e}")
        
        delete_schedule(schedule_id, None)
    
    def check_schedules(self):
        schedules = get_schedules()
        now = datetime.now(pytz.UTC)
        
        for schedule_data in schedules:
            if schedule_data['schedule_time'] <= now:
                self.execute_scheduled_task(
                    schedule_data['id'],
                    schedule_data['instance_id'],
                    schedule_data['action'],
                    schedule_data.get('dias_semana', ''),
                    schedule_data.get('horario', '')
                )
    
    def run_pending(self):
        while self.running:
            self.check_schedules()
            time.sleep(60)
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.run_pending)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

scheduler = Scheduler()