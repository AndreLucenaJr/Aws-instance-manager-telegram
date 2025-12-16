from datetime import datetime, timedelta
import pytz
from config import TZ_TIMEZONE

def parse_time_selection(data, chat_id):
    parts = data.split('_')
    
    if len(parts) < 4:
        return None
    
    time_option = parts[1]
    instance_id = parts[2]
    action = parts[3]
    
    tz = pytz.timezone(TZ_TIMEZONE)
    now = datetime.now(tz)
    
    if time_option.isdigit():
        hours = int(time_option)
        schedule_time = now + timedelta(hours=hours)
    elif time_option == 'tomorrow':
        hour = int(parts[2]) if len(parts) > 4 and parts[2].isdigit() else 8
        instance_id = parts[3] if len(parts) > 4 else parts[2]
        action = parts[4] if len(parts) > 4 else parts[3]
        
        tomorrow = now + timedelta(days=1)
        schedule_time = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
    else:
        return None
    
    return {
        'chat_id': chat_id,
        'instance_id': instance_id,
        'action': action,
        'schedule_time': schedule_time.astimezone(pytz.UTC)
    }