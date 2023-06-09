# version 0.1.0p - persistent tcp connection version
# version 0.1.0 - added axiom logging via python sdk
# version 0.0.2 - try is now catching sockets connect error | added -mode flag for "spam" or "once" sending
# version 0.0.1 - first working version, little error handling
# ----
# requirements
# pip install axiom-py python-dotenv APScheduler
# jason.chiu@salesforce.com

import argparse, textwrap
import socket
from datetime import datetime
import uuid # generate an id for each send
# need to pip install apscheduler, use Blocking so we can cancel their running from command line
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
import os
import axiom
import codecs # to read the sample file correctly \ is read as \\ by default in file.read()
import warnings # to suppress the deprecation warning from codecs
import time # to sleep and retry if needed

# setup for axiom logging
load_dotenv()
API_TOKEN = os.getenv('API_TOKEN')
axiom_client = axiom.Client(API_TOKEN)

# sample test message
sample_hl7 = """\x0bMSH|^~\&|Primary|PIEDMONT ATLANTA HOSPITAL|CL|PDMT|20200319170944|ADTPA|ADT^A01|203478||2.8.1|||||||||||
EVN|A01|20200319170944||ADT_EVENT|^ADT^PATIENT^ACCESS^^^^^PHC^^^^^PAH|20200319170941|
PID|1||E3866033^^^EPIC^MRN~900091282^^^EPI^MR||TEST^PAHSEVENACARDTELEM||19770919|F||White|8 TEST ST^^ATHENS^GA^30605^USA^P^^CLARKE|CLARKE|(999)999-9999^P^PH^^^999^9999999||ENG|MARRIED|UNKNOWN|1000046070|000-00-0000|||NOT HISPANIC||N||||||N||
PD1|||PIEDMONT ATLANTA HOSPITAL^^10500|1750426920^SMITH III^GEORGE^^^^^^NPI^^^^NPI~81923^SMITH III^GEORGE^^^^^^STARPC^^^^STARID~SMIGE^SMITH III^GEORGE^^^^^^MT^^^^MTID||||||||||||||
NK1|1|TEST^SPOUSE^^|Spouse||(888)888-8888^^PH^^^888^8888888||Emergency Contact 1|||||||||||||||||||||||||||
NK1|2|||^^^^^USA|||Employer||||||CDC||||||||||||||||||||7403|Full
PV1|1|INPATIENT|TA7B^0107028^0107028^PIEDMONT ATLANTA HOSPITAL^^^^^^^DEPID|UR|||1093782799^SMITH^ANITA^^^^^^NPI^^^^NPI~52228^SMITH^ANITA^^^^^^STARPC^^^^STARID|||General Med||||Phys/Clinic|||1093782799^SMITH^ANITA^^^^^^NPI^^^^NPI~52228^SMITH^ANITA^^^^^^STARPC^^^^STARID||2017417374|UHC||||||||||||||||||||||||20200319170941||||||||||
PV2||Priv||||||20200319|||||||||||||n|N||||||||||N|||||||||||||||||
OBX|1|NM|11156-7^LEUKOCYTES^LN||||||||I|
OBX|2|NM|11273-0^ERYTHROCYTES^LN||4.06|tera.l-1||N|||P|||201410060627
OBX|3|NM|20509-6^HEMOGLOBIN^LN||||||||I|
OBX|4|NM|20570-8^HEMATOCRIT^LN||40.1|%||N|||P|||201410060830
OBX|5|NM|11125-2^PLATELETS^LN||221|giga.l-1||N|||F|||201410060830
AL1|1|DA|32264^NO KNOWN ALLERGIES^||AAA|201410060830
DG1|1||^injury|injury||^10151;EPT||||||||||||||||||||
PR1|2234|M11|111^CODE151|COMMON PROCEDURES|198809081123
GT1|1|90389|TEST^PAHSEVENACARDTELEM^^||8 TEST ST^^ATHENS^GA^30605^USA^^^CLARKE|(999)999-9999^^^^^999^9999999||19770919|F|P/F|SLF|000-00-0000||||CDC|^^^^^USA|||Full|||||||||||||||||||||||||||||
IN1|1|1070006^UHC PPO|10700|UHC|^^ATLANTA^GA^^|||||||20200219||||TEST^PAHSEVENACARDTELEM^^|Self|19770919|8 TEST ST^^ATHENS^GA^30605^USA^^^CLARKE|||1|||||||||||||13603|23423||||||Full|F|^^^^^USA|||BOTH||
IN2||000-00-0000|||Payor Plan||||||||||||||||||||||||||||||||||||||||||||||||||||||||23423||(999)999-9999^^^^^999^9999999|||||||CDC\x1c\x0d"""

# connect and return the connection object
def mllp_connect(host,port):
  sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
  # set timeout as None makes it never timeout and sets socket to blocking mode
  sock.settimeout(None)
  sock.connect((host,port))
  return sock

# wrapper for smaller axiom log
def axiom_logger(logds,day,id,ts,ack,msg):
  axiom_client.ingest_events(
      dataset=logds,
      events=[
        {
          'testDay':day,
          'correlationId':id,
          'messageSentTimeStamp':ts,
          'acknowledgmentCode':ack,
          "message":msg
        }
      ])

# function for it
def mllp_transmit(sched,sock,message,log_dataset,add_input_padding='false',remove_output_padding='true'):
  # define vars
  id = str(uuid.uuid4())
  send_day = datetime.today().strftime('%Y-%m-%d')
  send_datetime = datetime.today().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
  # try grab the reply
  try:
    # add padding as needed
    message_temp = "\x0b" + message + "\x1c\x0d" if add_input_padding=='true' else message
    message_bytes = bytes(message_temp,'utf-8')
    # send message with our passed over socket object
    sock.sendall(message_bytes)
    # send the async log to axiom
    axiom_logger(log_dataset,send_day,id,send_datetime,'Sender_Sent',message_temp)
    # print(f'send datetime = {now_send}')
    # the reply in bytes
    reply_bytes = sock.recv(1024)
    recv_datetime = datetime.today().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    # print(f'recv datetime = {now_rec}')
    reply = reply_bytes.decode('utf-8')
    if(remove_output_padding=='true'):
      reply = reply.replace('\x0b','').replace('\x1c\x0d','')
    # print(f'reply = {reply}')
    # reply will now be csv style
    # with columns id, sendtime, recvtime, reply msg
    axiom_logger(log_dataset,send_day,id,recv_datetime,'Sender_Recv',reply)
    print(f'{id},{send_datetime},{recv_datetime},{reply}')
    return reply
  except Exception as e:
    # if retrying fails
    error_line = f'Error - {e}'
    axiom_logger(log_dataset,send_day,id,send_datetime,'Sender_Error',error_line)
    print(error_line)
    sock.close()
    # stop the scheduler
    if(sched):
      sched.shutdown(wait=False)
    # chatgpt tells me to re-throw an exception here so there's still an exception in the outer function
    raise e

# put this in a function so we can call it again for a broken connection
def schedule_spam(message,log_dataset,add_input_padding,remove_output_padding,sec_interval):
  sched = BlockingScheduler()
  # connect once
  s = mllp_connect(host,port)
  # run the mllp_transmit function on this interval
  job = sched.add_job(mllp_transmit, 
                args=[sched,s,message,log_dataset,add_input_padding,remove_output_padding], 
                trigger='interval', 
                seconds=sec_interval)
  sched.start()

# this function runs until explicitly shut down, the scheduler doesn't stop
# assume we want a minimum send rate of 1 per second
def mllp_spammer(sends_per_sec,host,port,message,log_dataset,add_input_padding='false',remove_output_padding='true',mode='spam'):
  if(mode=='spam'):
    # pass the per second interval to the schedule_spam function later
    sec_interval = 1 / sends_per_sec
    # wrap in 3 retries, need to +1 because the first time it'll just work
    retries = 3
    for i in range(retries+1):
      try:
        schedule_spam(message,log_dataset,add_input_padding,remove_output_padding,sec_interval)
      except Exception as e:  
        sleep_time = i+2
        retry_line = f'waiting {sleep_time} seconds, then retrying'
        axiom_logger(log_dataset,'','','','Sender_Error',retry_line)
        print(f'i={i},retry={retry_line},error={e}')
        time.sleep(sleep_time)

  # once mode
  else:
    s = mllp_connect(host,port)
    mllp_transmit(False,s,message,log_dataset,add_input_padding,remove_output_padding)
    try:
      while True:
        files = [x for x in os.listdir() if (not (x.startswith('.')) and not (x.endswith('.py')))]
        user_input = input(f"\n\nEnter a filename (in the same folder as this mllp_spammer script) to send as an MLLP message or 'quit' to end\nHere are some files you have: {files}\n")
        if(user_input.lower()=='quit'):
          s.close()
          break
        else:
          try:
            with open(user_input,'r') as file:
              # codecs.decode generates a warning because HL7 is messy DeprecationWarning: invalid escape sequence '\&'
              with warnings.catch_warnings():
                warnings.filterwarnings('ignore',category=DeprecationWarning)
                data = codecs.decode(file.read(),'unicode_escape')
              mllp_transmit(False,s,data,log_dataset,add_input_padding,remove_output_padding)
          except:
            print(f'{user_input} file not found')
    # close the socket with finally, finally hits every time, including ctrl+c
    finally:
      s.close()



# Initialize parser
parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# Adding optional argument
parser.add_argument("-sps", "--SendsPerSecond", help = textwrap.dedent('''Frequency of spamming MLLP transmit function, 
e.g. 1 = 1 per second, 2 = 2 per second, etc

'''))
parser.add_argument("-host", "--Host", required=True, help = textwrap.dedent('''MLLP host, can be example.com or ip address 1.1.1.1

'''))
parser.add_argument("-p", "--Port", required=True, help = textwrap.dedent('''MLLP port number, e.g. 5000

'''))
parser.add_argument("-m", "--Message", required=False, help = textwrap.dedent('''The MLLP message, look up HL7 docs for examples

'''))
parser.add_argument("-ld", "--LogDataset", required=True, help = textwrap.dedent('''The Axiom dataset name

'''))
parser.add_argument("-aip", "--AddInputPadding", required=False, help = textwrap.dedent('''If your message has no leading or trailing characters that HL7 needs, this adds them in \\x0b + input_message + \\x1c\\x0d

'''))
parser.add_argument("-rop", "--RemoveOutputPadding", required=False, help = textwrap.dedent('''View the output of the message without the output padding, \\x0b + input_message + \\x1c

'''))
parser.add_argument("-mode", "--Mode", required=False, help = textwrap.dedent('''Choose spam or once, spam mode will send messages every second and once mode will just send once

'''))
# Read arguments from command line
# all args come through as strings
args = parser.parse_args()
sps = int(args.SendsPerSecond)
host = args.Host
port = int(args.Port)
message = args.Message
mode = args.Mode
ld = args.LogDataset
# if args.Output:
#   print("Displaying Output as: % s" % args.Output)
# if args.SendsPerSecond:
#   print("Displaying SendsPerSecond as: % s" % args.SendsPerSecond)
#   print(type(args.SendsPerSecond))

mllp_spammer(sends_per_sec=sps,
             host=host,
             port=port,
             message=sample_hl7,
             log_dataset=ld,
             mode=mode
)
