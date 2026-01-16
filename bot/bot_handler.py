from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from aws.ec2_manager import EC2Manager
from database.postgres import add_schedule, get_schedules, delete_schedule, delete_all_schedules, update_next_schedule_time
from datetime import datetime, timedelta, time as dt_time
import pytz
import re
import os
import warnings

warnings.filterwarnings("ignore", message="If 'per_message=False'")
warnings.filterwarnings("ignore", message="If 'per_message=True'")

SET_TIME = 0

ec2_manager = EC2Manager()
AUTHORIZED_GROUP_ID = int(os.getenv('AUTHORIZED_GROUP_ID'))
user_schedule_data = {}

WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

async def verificar_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return update.effective_chat.type in ['group', 'supergroup'] and update.effective_chat.id == AUTHORIZED_GROUP_ID

async def executar_agendamento(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    schedule = job.data
    
    try:
        instance_id = schedule['instance_id']
        action = schedule['action']
        
        if instance_id == 'all':
            if action == 'start':
                results = ec2_manager.start_all_instances()
            else:
                results = ec2_manager.stop_all_instances()
            
            if results:
                mensagem_resultado = f"✅ SCHEDULE EXECUTED!\n\nAction: {action.upper()} ALL\nResults:\n" + "\n".join(results)
            else:
                mensagem_resultado = f"✅ SCHEDULE EXECUTED!\n\nAction: {action.upper()} ALL\nNo instances processed."
        else:
            if action == 'start':
                success, result = ec2_manager.start_instance(instance_id)
            else:
                success, result = ec2_manager.stop_instance(instance_id)
            
            if success:
                mensagem_resultado = f"✅ SCHEDULE EXECUTED!\n\nInstance: {instance_id}\nAction: {action.upper()}\nStatus: Success"
            else:
                mensagem_resultado = f"✅ SCHEDULE EXECUTED!\n\nInstance: {instance_id}\nAction: {action.upper()}\nStatus: {result}"
        
        await context.bot.send_message(chat_id=AUTHORIZED_GROUP_ID, text=mensagem_resultado)
        
        dias_semana = schedule.get('dias_semana', '')
        horario = schedule.get('horario', '')
        
        if dias_semana and horario:
            tz = pytz.timezone('America/Sao_Paulo')
            agora = datetime.now(tz)
            
            proxima_data = None
            for i in range(1, 366):
                data_teste = agora + timedelta(days=i)
                dias_numeros = [int(d) for d in dias_semana.split(',') if d]
                
                if data_teste.weekday() in dias_numeros:
                    proxima_data = data_teste
                    break
            
            if proxima_data:
                hora, minuto = map(int, horario.split(':'))
                data_agendamento = datetime.combine(proxima_data.date(), dt_time(hora, minuto))
                data_agendamento = tz.localize(data_agendamento)
                data_agendamento_utc = data_agendamento.astimezone(pytz.UTC)
                
                if update_next_schedule_time(schedule['id'], data_agendamento_utc):
                    schedule['schedule_time'] = data_agendamento_utc
                    
                    atraso = (data_agendamento_utc - datetime.now(pytz.UTC)).total_seconds()
                    
                    if atraso > 0 and context.application and context.application.job_queue:
                        existing_jobs = context.application.job_queue.get_jobs_by_name(str(schedule['id']))
                        for existing_job in existing_jobs:
                            existing_job.schedule_removal()
                        context.application.job_queue.run_once(
                            executar_agendamento,
                            when=atraso,
                            name=str(schedule['id']),
                            data=schedule
                        )
        
    except Exception as e:
        print(f"ERROR EXECUTING SCHEDULE: {e}")
        try:
            await context.bot.send_message(
                chat_id=AUTHORIZED_GROUP_ID, 
                text=f"❌ ERROR EXECUTING SCHEDULE!\n\nError: {str(e)}"
            )
        except:
            pass

def carregar_agendamentos(application: Application):
    schedules = get_schedules()
    agora_utc = datetime.now(pytz.UTC)
    
    for schedule in schedules:
        schedule_time = schedule['schedule_time']
        
        if isinstance(schedule_time, datetime):
            if schedule_time.tzinfo is None:
                schedule_time = pytz.UTC.localize(schedule_time)
            
            if schedule_time > agora_utc:
                atraso = (schedule_time - agora_utc).total_seconds()
                
                if atraso > 0:
                    application.job_queue.run_once(
                        executar_agendamento,
                        when=atraso,
                        name=str(schedule['id']),
                        data=schedule
                    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_grupo(update, context):
        return
    
    keyboard = [
        [InlineKeyboardButton("Manage Instances", callback_data='manage_instances')],
        [InlineKeyboardButton("Schedule Tasks", callback_data='schedule_menu')],
        [InlineKeyboardButton("View Schedules", callback_data='view_schedules')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Choose an option:', reply_markup=reply_markup)

async def start_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if not await verificar_grupo(update, context):
        await query.answer("❌ Access Denied.", show_alert=True)
        return
    
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Manage Instances", callback_data='manage_instances')],
        [InlineKeyboardButton("Schedule Tasks", callback_data='schedule_menu')],
        [InlineKeyboardButton("View Schedules", callback_data='view_schedules')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Choose an option:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if not await verificar_grupo(update, context):
        await query.answer("❌ Access Denied.", show_alert=True)
        return
    
    await query.answer()
    data = query.data
    
    if data == 'manage_instances':
        await show_instances_menu(query)
    elif data == 'schedule_menu':
        await show_schedule_menu(query)
    elif data == 'view_schedules':
        await show_schedules(query)
    elif data.startswith('instance_'):
        parts = data.split('_')
        if len(parts) >= 3:
            instance_id = '_'.join(parts[1:-1])
            action = parts[-1]
            await handle_instance_action(query, instance_id, action)
    elif data == 'start_all':
        await start_all_instances(query)
    elif data == 'stop_all':
        await stop_all_instances(query)
    elif data.startswith('schedule_action_'):
        parts = data.split('_')
        instance_id = parts[2] if len(parts) > 2 else 'all'
        action = parts[3]
        user_id = query.from_user.id
        user_schedule_data[user_id] = {
            'instance_id': instance_id,
            'action': action,
            'dias_semana': [],
            'horario': None
        }
        await escolher_horario_menu(query)
    elif data.startswith('delete_schedule_'):
        schedule_id = int(data.split('_')[2])
        
        if context.application and context.application.job_queue:
            jobs = context.application.job_queue.get_jobs_by_name(str(schedule_id))
            for job in jobs:
                job.schedule_removal()
        
        if delete_schedule(schedule_id, AUTHORIZED_GROUP_ID):
            await query.edit_message_text(f"✅ Schedule {schedule_id} deleted.")
        else:
            await query.edit_message_text("❌ Could not delete.")
    elif data == 'delete_all_schedules':
        schedules = get_schedules(AUTHORIZED_GROUP_ID)
        if context.application and context.application.job_queue:
            for schedule in schedules:
                jobs = context.application.job_queue.get_jobs_by_name(str(schedule['id']))
                for job in jobs:
                    job.schedule_removal()
        
        count = delete_all_schedules(AUTHORIZED_GROUP_ID)
        await query.edit_message_text(f"✅ {count} schedules deleted.")
    elif data == 'back_to_main':
        await start_from_callback(update, context)
    elif data == 'digitar_horario':
        await pedir_horario_digitado(query)
    elif data == 'voltar_horario':
        await escolher_horario_menu(query)
    elif data.startswith('dia_'):
        await handle_dia_selecionado(query, data)
    elif data in ['dias_uteis', 'fins_semana', 'todos_dias']:
        await handle_padrao_dias(query, data)
    elif data == 'finalizar_dias':
        await mostrar_resumo_agendamento(query)
    elif data == 'confirmar_agendamento':
        await confirmar_agendamento(query, context)
    elif data == 'cancelar_agendamento':
        user_id = query.from_user.id
        if user_id in user_schedule_data:
            del user_schedule_data[user_id]
        await start_from_callback(update, context)
    elif data == 'escolher_horario':
        await escolher_horario_menu(query)
    elif data == 'escolher_dias':
        await escolher_dias_semana_menu(query)
    elif data == 'voltar_opcoes':
        user_id = query.from_user.id
        if user_id in user_schedule_data:
            dados = user_schedule_data[user_id]
            await ask_schedule_options(query, dados['instance_id'], dados['action'])

async def show_instances_menu(query):
    instances = ec2_manager.get_all_instances()
    keyboard = []
    
    for instance in instances:
        keyboard.append([
            InlineKeyboardButton(f"{instance['name']} ({instance['id']}) - {instance['state']}", callback_data=f"instance_{instance['id']}_details")
        ])
    
    keyboard.append([
        InlineKeyboardButton("Start All", callback_data='start_all'),
        InlineKeyboardButton("Stop All", callback_data='stop_all')
    ])
    keyboard.append([InlineKeyboardButton("Back", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('EC2 Instances:', reply_markup=reply_markup)

async def show_schedule_menu(query):
    instances = ec2_manager.get_all_instances()
    keyboard = []
    
    for instance in instances:
        keyboard.append([
            InlineKeyboardButton(f"📅 {instance['name']}", callback_data=f"schedule_action_{instance['id']}_start"),
            InlineKeyboardButton(f"🛑 {instance['name']}", callback_data=f"schedule_action_{instance['id']}_stop")
        ])
    
    keyboard.append([
        InlineKeyboardButton("📅 All - Start", callback_data='schedule_action_all_start'),
        InlineKeyboardButton("🛑 All - Stop", callback_data='schedule_action_all_stop')
    ])
    keyboard.append([InlineKeyboardButton("Back", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Schedule action for:', reply_markup=reply_markup)

async def ask_schedule_options(query, instance_id, action):
    instance_text = "All instances" if instance_id == 'all' else f"Instance: {instance_id}"
    action_text = "▶️ START" if action == 'start' else "⏸️ STOP"
    
    keyboard = [
        [InlineKeyboardButton("⌨️ Enter Time", callback_data='digitar_horario')],
        [InlineKeyboardButton("📅 Choose Days", callback_data='escolher_dias')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancelar_agendamento')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 Configure Schedule\n{instance_text}\nAction: {action_text}\nConfigure schedule:",
        reply_markup=reply_markup
    )

async def escolher_horario_menu(query):
    keyboard = [
        [InlineKeyboardButton("⌨️ Enter Time", callback_data='digitar_horario')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancelar_agendamento')]
    ]
    
    user_id = query.from_user.id
    instance_text = "All instances"
    action_text = "START"
    
    if user_id in user_schedule_data:
        dados = user_schedule_data[user_id]
        instance_text = "All" if dados['instance_id'] == 'all' else f"Instance: {dados['instance_id']}"
        action_text = "▶️ START" if dados['action'] == 'start' else "⏸️ STOP"
    
    await query.edit_message_text(
        f"⏰ STEP 1: SELECT TIME\n\n{instance_text}\nAction: {action_text}\nClick 'Enter Time' to set time:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def pedir_horario_digitado(query):
    await query.edit_message_text("⌨️ Enter time (HH:MM):\nExample: 09:30, 14:00\n/cancel to cancel.")
    return SET_TIME

async def handle_horario_digitado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_grupo(update, context):
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    horario_texto = update.message.text.strip()
    
    if horario_texto.lower() == '/cancel':
        if user_id in user_schedule_data:
            del user_schedule_data[user_id]
        await update.message.reply_text("❌ Canceled.")
        return ConversationHandler.END
    
    if re.match(r'^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$', horario_texto):
        hora, minuto = map(int, horario_texto.split(':'))
        horario = dt_time(hora, minuto)
        
        if user_id in user_schedule_data:
            user_schedule_data[user_id]['horario'] = horario
            await update.message.reply_text(f"✅ Time: {horario_texto}")
            
            await escolher_dias_semana_menu_after_digitado(update, user_id, horario_texto)
        else:
            await update.message.reply_text("❌ Session expired.")
    else:
        await update.message.reply_text("❌ Invalid format! Use HH:MM")
        return SET_TIME
    
    return ConversationHandler.END

async def escolher_dias_semana_menu_after_digitado(update, user_id, horario_texto):
    if user_id not in user_schedule_data:
        await update.message.reply_text("❌ Session expired.")
        return
    
    dados = user_schedule_data[user_id]
    dias_menu_items = [
        (WEEKDAYS[0], 0, 'dia_0'),
        (WEEKDAYS[1], 1, 'dia_1'),
        (WEEKDAYS[2], 2, 'dia_2'),
        (WEEKDAYS[3], 3, 'dia_3'),
        (WEEKDAYS[4], 4, 'dia_4'),
        (WEEKDAYS[5], 5, 'dia_5'),
        (WEEKDAYS[6], 6, 'dia_6'),
    ]
    
    keyboard = []
    for nome_dia, numero_dia, callback in dias_menu_items:
        emoji = '✅' if numero_dia in dados.get('dias_semana', []) else '⬜'
        keyboard.append([InlineKeyboardButton(f"{emoji} {nome_dia}", callback_data=callback)])
    
    keyboard.append([
        InlineKeyboardButton("✅ Business Days", callback_data='dias_uteis'),
        InlineKeyboardButton("🏖️ Weekend", callback_data='fins_semana'),
        InlineKeyboardButton("📅 All Days", callback_data='todos_dias')
    ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Finish", callback_data='finalizar_dias'),
        InlineKeyboardButton("↩️ Back", callback_data='voltar_horario')
    ])
    
    instance_text = "All" if dados['instance_id'] == 'all' else f"Instance: {dados['instance_id']}"
    action_text = "▶️ START" if dados['action'] == 'start' else "⏸️ STOP"
    
    await update.message.reply_text(
        f"📅 STEP 2: SELECT DAYS\n\n{instance_text}\nAction: {action_text}\nTime: {horario_texto}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def escolher_dias_semana_menu(query):
    user_id = query.from_user.id
    
    if user_id not in user_schedule_data:
        await query.edit_message_text("❌ Session expired.")
        return
    
    dados = user_schedule_data[user_id]
    dias_menu_items = [
        (WEEKDAYS[0], 0, 'dia_0'),
        (WEEKDAYS[1], 1, 'dia_1'),
        (WEEKDAYS[2], 2, 'dia_2'),
        (WEEKDAYS[3], 3, 'dia_3'),
        (WEEKDAYS[4], 4, 'dia_4'),
        (WEEKDAYS[5], 5, 'dia_5'),
        (WEEKDAYS[6], 6, 'dia_6'),
    ]
    
    keyboard = []
    for nome_dia, numero_dia, callback in dias_menu_items:
        emoji = '✅' if numero_dia in dados.get('dias_semana', []) else '⬜'
        keyboard.append([InlineKeyboardButton(f"{emoji} {nome_dia}", callback_data=callback)])
    
    keyboard.append([
        InlineKeyboardButton("✅ Business Days", callback_data='dias_uteis'),
        InlineKeyboardButton("🏖️ Weekend", callback_data='fins_semana'),
        InlineKeyboardButton("📅 All Days", callback_data='todos_dias')
    ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Finish", callback_data='finalizar_dias'),
        InlineKeyboardButton("↩️ Back", callback_data='voltar_horario')
    ])
    
    instance_text = "All" if dados['instance_id'] == 'all' else f"Instance: {dados['instance_id']}"
    action_text = "▶️ START" if dados['action'] == 'start' else "⏸️ STOP"
    horario_text = dados['horario'].strftime("%H:%M") if dados['horario'] else "Not set"
    
    await query.edit_message_text(
        f"📅 STEP 2: SELECT DAYS\n\n{instance_text}\nAction: {action_text}\nTime: {horario_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_dia_selecionado(query, data):
    user_id = query.from_user.id
    
    if data.startswith('dia_'):
        dia_numero = int(data.replace('dia_', ''))
        
        if user_id in user_schedule_data:
            if 'dias_semana' not in user_schedule_data[user_id]:
                user_schedule_data[user_id]['dias_semana'] = []
            
            dias = user_schedule_data[user_id]['dias_semana']
            
            if dia_numero in dias:
                dias.remove(dia_numero)
            else:
                dias.append(dia_numero)
            
            await escolher_dias_semana_menu(query)

async def handle_padrao_dias(query, data):
    user_id = query.from_user.id
    
    if user_id not in user_schedule_data:
        await query.edit_message_text("❌ Session expired.")
        return
    
    if data == 'dias_uteis':
        user_schedule_data[user_id]['dias_semana'] = [0, 1, 2, 3, 4]
    elif data == 'fins_semana':
        user_schedule_data[user_id]['dias_semana'] = [5, 6]
    elif data == 'todos_dias':
        user_schedule_data[user_id]['dias_semana'] = list(range(7))
    
    await mostrar_resumo_agendamento(query)

async def mostrar_resumo_agendamento(query):
    user_id = query.from_user.id
    
    if user_id not in user_schedule_data:
        await query.edit_message_text("❌ Session expired.")
        return
    
    dados = user_schedule_data[user_id]
    instance_text = "All" if dados['instance_id'] == 'all' else f"Instance: {dados['instance_id']}"
    action_text = "▶️ START" if dados['action'] == 'start' else "⏸️ STOP"
    horario_text = dados['horario'].strftime("%H:%M") if dados['horario'] else "Not set"
    
    dias_text = "Not set"
    if dados['dias_semana']:
        dias_text = ', '.join([WEEKDAYS[d] for d in sorted(dados['dias_semana'])])
    
    completo = dados['horario'] is not None and len(dados['dias_semana']) > 0
    
    keyboard = []
    if not completo:
        if not dados['horario']:
            keyboard.append([InlineKeyboardButton("⌨️ Enter Time", callback_data='voltar_horario')])
        if not dados['dias_semana']:
            keyboard.append([InlineKeyboardButton("📅 Set Days", callback_data='escolher_dias')])
    else:
        keyboard.append([InlineKeyboardButton("✅ CONFIRM", callback_data='confirmar_agendamento')])
    
    keyboard.append([
        InlineKeyboardButton("↩️ Back", callback_data='escolher_dias'),
        InlineKeyboardButton("❌ Cancel", callback_data='cancelar_agendamento')
    ])
    
    status = "✅ READY" if completo else "⚠️ INCOMPLETE"
    
    await query.edit_message_text(
        f"📋 SUMMARY\n{status}\n\n{instance_text}\nAction: {action_text}\nTime: {horario_text}\nDays: {dias_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirmar_agendamento(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    
    if user_id not in user_schedule_data:
        await query.edit_message_text("❌ Session expired.")
        return
    
    dados = user_schedule_data[user_id]
    
    if not dados['horario'] or not dados['dias_semana']:
        await query.edit_message_text("❌ Incomplete configuration!")
        return
    
    tz = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(tz)
    
    group_id = AUTHORIZED_GROUP_ID

    for i in range(8):
        data_teste = agora + timedelta(days=i)
        if data_teste.weekday() in dados['dias_semana']:
            data_agendamento = datetime.combine(data_teste.date(), dados['horario'])
            data_agendamento = tz.localize(data_agendamento)
            data_agendamento_utc = data_agendamento.astimezone(pytz.UTC)
            
            schedule_id = add_schedule(
                group_id=group_id,
                instance_id=dados['instance_id'],
                action=dados['action'],
                schedule_time=data_agendamento_utc,
                dias_semana=','.join(map(str, dados['dias_semana'])),
                horario=dados['horario'].strftime("%H:%M")
            )
            
            schedule_data = {
                'id': schedule_id,
                'chat_id': group_id,
                'instance_id': dados['instance_id'],
                'action': dados['action'],
                'dias_semana': ','.join(map(str, dados['dias_semana'])),
                'horario': dados['horario'].strftime("%H:%M")
            }
            
            atraso = (data_agendamento_utc - datetime.now(pytz.UTC)).total_seconds()
            
            if atraso > 0 and context.application and context.application.job_queue:
                context.application.job_queue.run_once(
                    executar_agendamento,
                    when=atraso,
                    name=str(schedule_id),
                    data=schedule_data
                )
            
            del user_schedule_data[user_id]
            
            data_formatada = data_agendamento.strftime("%d/%m/%Y at %H:%M")
            dias_text = ', '.join([WEEKDAYS[d] for d in dados['dias_semana']])
            
            await query.edit_message_text(
                f"✅ SCHEDULE CONFIRMED!\n\n"
                f"📋 Details:\n"
                f"• {'All' if dados['instance_id'] == 'all' else 'Instance: ' + dados['instance_id']}\n"
                f"• Action: {'START' if dados['action'] == 'start' else 'STOP'}\n"
                f"• Time: {dados['horario'].strftime('%H:%M')}\n"
                f"• Days: {dias_text}\n"
                f"• Next execution: {data_formatada}\n\n"
                f"ID: {schedule_id}\n\n"
                f"✅ You will be notified on the group when executed!"
            )
            return
    
    await query.edit_message_text("❌ Error calculating date.")

async def handle_instance_action(query, instance_id, action):
    if action == 'start':
        success, message = ec2_manager.start_instance(instance_id)
        await query.edit_message_text(message)
    elif action == 'stop':
        success, message = ec2_manager.stop_instance(instance_id)
        await query.edit_message_text(message)
    elif action == 'details':
        instances = ec2_manager.get_all_instances()
        instance = next((i for i in instances if i['id'] == instance_id), None)
        
        if instance:
            keyboard = [
                [
                    InlineKeyboardButton("▶️ Start", callback_data=f"instance_{instance_id}_start"),
                    InlineKeyboardButton("⏸️ Stop", callback_data=f"instance_{instance_id}_stop")
                ],
                [InlineKeyboardButton("Back", callback_data='manage_instances')]
            ]
            await query.edit_message_text(
                f"Instance: {instance['name']}\nID: {instance_id}\nState: {instance['state']}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def start_all_instances(query):
    results = ec2_manager.start_all_instances()
    message = "Results:\n" + "\n".join(results) if results else "No instances to start."
    await query.edit_message_text(message[:4000])

async def stop_all_instances(query):
    results = ec2_manager.stop_all_instances()
    message = "Results:\n" + "\n".join(results) if results else "No instances to stop."
    await query.edit_message_text(message[:4000])

async def show_schedules(query):
    group_id = AUTHORIZED_GROUP_ID
    schedules = get_schedules(group_id)
    
    if not schedules:
        keyboard = [
            [InlineKeyboardButton("↩️ Back", callback_data='back_to_main')]
        ]
        await query.edit_message_text("📭 No schedules found.", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    message = "📅 SCHEDULES:\n\n"
    
    for schedule in schedules:
        schedule_time = schedule['schedule_time']
        if isinstance(schedule_time, datetime) and schedule_time.tzinfo is None:
            schedule_time = pytz.UTC.localize(schedule_time)
        
        schedule_time_local = schedule_time.astimezone(pytz.timezone('America/Sao_Paulo'))
        horario_agendamento = schedule['horario'] if 'horario' in schedule and schedule['horario'] else schedule_time_local.strftime('%H:%M')
        
        dias_text = ""
        if 'dias_semana' in schedule and schedule['dias_semana']:
            try:
                dias_numeros = [int(d) for d in schedule['dias_semana'].split(',') if d]
                dias_text = f"\n• Days: {', '.join([WEEKDAYS[d] for d in dias_numeros])}"
            except:
                pass
        
        message += f"🆔 ID: {schedule['id']}\n"
        message += f"• Instance: {schedule['instance_id']}\n"
        message += f"• Action: {schedule['action'].upper()}\n"
        message += f"• Time: {horario_agendamento}\n"
        if dias_text:
            message += dias_text
        message += f"• Next: {schedule_time_local.strftime('%d/%m')}\n"
        message += "-" * 30 + "\n"
    
    keyboard = []
    for schedule in schedules:
        keyboard.append([InlineKeyboardButton(f"🗑️ Delete {schedule['id']}", callback_data=f"delete_schedule_{schedule['id']}")])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Delete All", callback_data='delete_all_schedules'),
        InlineKeyboardButton("↩️ Back", callback_data='back_to_main')
    ])
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_grupo(update, context):
        return
    
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if user_id in user_schedule_data and not text.startswith('/'):
        if 'horario' not in user_schedule_data[user_id] or not user_schedule_data[user_id]['horario']:
            await handle_horario_digitado(update, context)

def setup_handlers(application: Application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(pedir_horario_digitado, pattern='^digitar_horario$')],
        states={
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_horario_digitado)]
        },
        fallbacks=[CommandHandler('cancelar', lambda update, context: ConversationHandler.END)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    carregar_agendamentos(application)