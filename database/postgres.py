import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True  
    cur = conn.cursor()
    
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                instance_id TEXT,
                action TEXT,
                schedule_time TIMESTAMP,
                dias_semana TEXT,           
                horario TEXT,              
                repetir BOOLEAN DEFAULT FALSE,  
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Tabela 'schedules' verificada/criada.")
        
    except Exception as e:
        print(f"Erro ao criar tabela: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def check_and_fix_columns():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True 
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'schedules')")
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            init_db()
            return
        
        
        columns_to_check = [
            ('dias_semana', 'TEXT'),
            ('horario', 'TEXT'),
            ('repetir', 'BOOLEAN DEFAULT FALSE')
        ]
        
        for column_name, column_type in columns_to_check:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='schedules' AND column_name=%s
            """, (column_name,))
            
            if not cur.fetchone():
                
                try:
                    cur.execute(f"ALTER TABLE schedules ADD COLUMN {column_name} {column_type}")
                except Exception as e:
                    conn.rollback()
            else:
                break
        
        print("Verificação de colunas concluída!")
        
    except Exception as e:
        print(f"Erro ao verificar/consertar colunas: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def add_schedule(chat_id, instance_id, action, schedule_time, dias_semana=None, horario=None, repetir=False):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        check_and_fix_columns()
        
        cur.execute(
            '''INSERT INTO schedules 
               (chat_id, instance_id, action, schedule_time, dias_semana, horario, repetir) 
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id''',
            (chat_id, instance_id, action, schedule_time, dias_semana, horario, repetir)
        )
        
        schedule_id = cur.fetchone()[0]
        conn.commit()
        return schedule_id
        
    except psycopg2.Error as e:
        conn.rollback()
        
        if "column" in str(e) and "does not exist" in str(e):
            cur.close()
            conn.close()
            
            force_recreate_table()
            
            return add_schedule(chat_id, instance_id, action, schedule_time, dias_semana, horario, repetir)
        raise
        
    except Exception as e:
        conn.rollback()
        raise
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

def force_recreate_table():

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) FROM schedules")
        count = cur.fetchone()[0]
        
        if count > 0:
            resposta = input("Continuar? (s/n): ")
            if resposta.lower() != 's':
                print("Operação cancelada.")
                return

        cur.execute('DROP TABLE IF EXISTS schedules CASCADE')
        print("Tabela antiga removida.")
        
        cur.execute('''
            CREATE TABLE schedules (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                instance_id TEXT,
                action TEXT,
                schedule_time TIMESTAMP,
                dias_semana TEXT,           
                horario TEXT,              
                repetir BOOLEAN DEFAULT FALSE,  
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    except Exception as e:
        print(f"Erro ao recriar tabela: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def get_schedules(chat_id=None):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if chat_id:
            cur.execute('SELECT * FROM schedules WHERE chat_id = %s ORDER BY schedule_time', (chat_id,))
        else:
            cur.execute('SELECT * FROM schedules ORDER BY schedule_time')
        
        schedules = cur.fetchall()
        return schedules
    except psycopg2.Error as e:
        print(f"Erro ao buscar agendamentos: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_repeating_schedules():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute('SELECT * FROM schedules WHERE repetir = TRUE ORDER BY schedule_time')
        schedules = cur.fetchall()
        return schedules
    except psycopg2.Error as e:
        print(f"Erro ao buscar agendamentos repetitivos: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def update_next_schedule_time(schedule_id, next_time):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    try:
        cur.execute(
            'UPDATE schedules SET schedule_time = %s WHERE id = %s',
            (next_time, schedule_id)
        )
        conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"Erro ao atualizar horário: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def delete_schedule(schedule_id, chat_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM schedules WHERE id = %s AND chat_id = %s', (schedule_id, chat_id))
        rows_deleted = cur.rowcount
        conn.commit()
        return rows_deleted > 0
    except psycopg2.Error as e:
        print(f"Erro ao deletar agendamento: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def delete_all_schedules(chat_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM schedules WHERE chat_id = %s', (chat_id,))
        rows_deleted = cur.rowcount
        conn.commit()
        return rows_deleted
    except psycopg2.Error as e:
        print(f"Erro ao deletar todos os agendamentos: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()
        conn.close()

def get_schedule_by_id(schedule_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute('SELECT * FROM schedules WHERE id = %s', (schedule_id,))
        schedule = cur.fetchone()
        return schedule
    except psycopg2.Error as e:
        print(f"Erro ao buscar agendamento por ID: {e}")
        return None
    finally:
        cur.close()
        conn.close()

