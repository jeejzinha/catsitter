import machine      
import time         
from machine import Pin, PWM
from umqtt.simple import MQTTClient
import network

WIFI_SSID = "NOME_DO_SEU_WIFI"
WIFI_SENHA = "SENHA_DO_SEU_WIFI"
BROKER_MQTT = "broker.hivemq.com"   
MEU_ID = "unicjhernandez"              

TOPICO_PRESENCA = "/fei/" + MEU_ID + "/presenca_interno"      
TOPICO_SOM      = "/fei/" + MEU_ID + "/som"                   
TOPICO_RACAO_STATUS = "/fei/" + MEU_ID + "/status_racao"      
TOPICO_COMANDO_RACAO = "/fei/" + MEU_ID + "/comando_racao"    
TOPICO_COMANDO_ESP32 = "/fei/" + MEU_ID + "/esp32"            

PINO_PIR = 12          
PINO_SOM = 14          
PINO_SERVO = 27       
PINO_RELE = 26         

pir = Pin(PINO_PIR, Pin.IN)          
som = Pin(PINO_SOM, Pin.IN)          
rele = Pin(PINO_RELE, Pin.OUT)       
rele.value(0)                        

servo = PWM(Pin(PINO_SERVO), freq=50)  

def abrir_porta():
    servo.duty(115)

def fechar_porta():
    servo.duty(40)


porta_aberta = False        
racao_ativa = False         


ULTIMO_ACIONAMENTO_PIR = 0
COOLDOWN_PIR_MS = 4000      
INTERVALO_PUBLICACAO_MS = 3000
ultima_publicacao = 0


def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_SENHA)
        while not wlan.isconnected():
            time.sleep(0.5)   
    print("Wifi conectado:", wlan.ifconfig())



def quando_chegar_mensagem(topico, mensagem):
    global racao_ativa, INTERVALO_PUBLICACAO_MS

    topico = topico.decode()          
    mensagem = mensagem.decode()

    
    if topico == TOPICO_COMANDO_RACAO:
        if mensagem == "Ativar":
            rele.value(1)              
            racao_ativa = True
            print("Racao ATIVADA")
        elif mensagem == "Desativar":
            rele.value(0)              
            racao_ativa = False
            print("Racao DESATIVADA")
        else:
            print("Comando de racao invalido, ignorado:", mensagem)

    
    elif topico == TOPICO_COMANDO_ESP32:
       
        if mensagem.startswith("Atualizar:"):
            try:
                novo_valor = int(mensagem.split(":")[1])  
                if 2 <= novo_valor <= 10:
                    INTERVALO_PUBLICACAO_MS = novo_valor * 1000
                    print("Intervalo de publicacao atualizado para", novo_valor, "segundos")
                else:
                    print("Valor fora do permitido (2 a 10), ignorado")
            except:
                print("Comando 'Atualizar' mal formatado, ignorado")
        else:
            print("Comando de ESP32 invalido, ignorado:", mensagem)



def conectar_mqtt():
    cliente = MQTTClient("esp32_" + MEU_ID, BROKER_MQTT)
    cliente.set_callback(quando_chegar_mensagem)
    cliente.connect()
    cliente.subscribe(TOPICO_COMANDO_RACAO)
    cliente.subscribe(TOPICO_COMANDO_ESP32)
    print("MQTT conectado e inscrito nos topicos de comando")
    return cliente



conectar_wifi()
cliente_mqtt = conectar_mqtt()

while True:


    try:
        cliente_mqtt.check_msg()
    except Exception as erro:
        print("Erro no MQTT, tentando reconectar:", erro)
        try:
            cliente_mqtt = conectar_mqtt()
        except Exception as erro2:
            print("Reconexao falhou, tentando de novo na proxima volta:", erro2)

    agora = time.ticks_ms()  


    tempo_desde_ultimo_pir = time.ticks_diff(agora, ULTIMO_ACIONAMENTO_PIR)

    if pir.value() == 1 and tempo_desde_ultimo_pir > COOLDOWN_PIR_MS:
        ULTIMO_ACIONAMENTO_PIR = agora   

        if porta_aberta == False:
            abrir_porta()
            porta_aberta = True
            print("Gato detectado -> porta ABERTA")
        else:
            fechar_porta()
            porta_aberta = False
            print("Gato detectado de novo -> porta FECHADA")


    tempo_desde_ultima_pub = time.ticks_diff(agora, ultima_publicacao)

    if tempo_desde_ultima_pub > INTERVALO_PUBLICACAO_MS:
        ultima_publicacao = agora

        try:
            
            cliente_mqtt.publish(TOPICO_PRESENCA, str(int(porta_aberta)))

            
            cliente_mqtt.publish(TOPICO_SOM, str(som.value()))

           
            cliente_mqtt.publish(TOPICO_RACAO_STATUS, str(int(racao_ativa)))

            print("Status publicado no MQTT")
        except Exception as erro:
            print("Erro ao publicar, vai tentar de novo no proximo ciclo:", erro)
