# mllp-spammer

## Summary
Mllp_spammer.py is a load testing MLLP (Minimal Lower Layer Protocol) tool for sending HL7 messages over the TCP protocol.

It’s open source and here is the code

At this stage there are 3 separate Apps, with the future roadmap being to make one app with the appropriate flags. During my own usage I found this route quicker and less muddy to use.
| App Name                      | Description                 | Notes                                                                                                                                                                                                                                                                             |
|-------------------------------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mllp_spammer.py               | The simplest one            | Non-persistent connections Prints output Dependencies: ```pip install APScheduler```                                                                                                                                                                                                    |
| Mllp_spammer_axiom.py         | Added logging to Axiom.co   | Non-persistent connections Sends logs to Axiom via Axiom SDK (Async HTTP req) Ability to send text file in “once” mode ```Dependencies: pip install axiom-py python-dotenv APScheduler```                                                                                               |
| Mllp_spammer_axiom_persist.py | Uses persistent connections | Persistent connections Sends logs to Axiom via Axiom SDK (Async HTTP req) Ability to send text file in “once” mode Has a primitive retry mechanism if disconnected. Retries 3 times, waits 2,3,4 seconds, then stops Dependencies: ```pip install axiom-py python-dotenv APScheduler``` |


The purpose of this App is to test MLLP and HL7 messages, but it can be used to test any TCP connections. It uses the generic Python Sockets library

## Example AWS-Mulesoft Architecture

In this Architecture, we run Mllp_spammer.py inside an EC2 machine in the AWS VPC.
Our target MLLP receiver is a Mule App inside Cloudhub 2.0 Private Space (which is another VPC). As this is a Private Space, we have no access via the internet and need to set up routing via AWS Transit Gateway. Find more information on setting up AWS Transit Gateway [here].

In the cases where we use Axiom.co to log messages, both the AWS VPC and Cloudhub 2.0 Private Space need outbound access to the internet.


## How to Use
Copy the Python file you want to use to your machine.
If you’re using an Axiom version
Sign up to Axiom hobby tier. You’ll get 2 datasets and at least 100GB to play with
Create API Token >> Settings > API tokens > New API Token
Install the dependencies and create “.env” file with the Axiom API_TOKEN=[my_token_value]
Install Python dependencies (Assumes Python version 3+)
Run via command line python3 mllp_spammer.py [flags] 
More details below

### Scenario 1 - mllp_spammer.py basic usage
Once mode
```
python3 mllp_spammer.py -host localhost -p 51961 -sps 1 -mode once
```

This sends the hardcoded MLLP message to localhost:51961 one time.
There are 3 required flags
-host (Host) = can be localhost, ip address or uri name
-p (Port Number)
-sps (Sends Per Second) = 1 to 10 is a good range to use, because the App waits for a reply before sending the next message
-mode (spam or once) - this is not required but I like to see it. Spam keeps sending and Once sends once

The way the non-persistent connections work is:
Socket opened
Message sent
Socket closed

Inside the App there is a test HL7 message in the ADT format. I’m not a healthcare expert, so I can’t tell you more than that.

You can also try:
```python3 mllp_spammer.py -host tcpbin.com -p 4242 -mode once```
Tcpbin.com is a site that reflects back what you sent via tcp on port 4242.

Spam mode
```python3 mllp_spammer.py -host localhost -p 51961 -sps 1 -mode spam```

Spam mode runs a blocking scheduler from the APScheduler library and runs indefinitely.
In order to stop the App when it’s running in the foreground, press Ctrl+C

A blocking scheduler uses 1 thread and waits for a reply before sending the next message. If there’s a slow reply and the scheduler tries to send, you’ll get an error message and it’ll continue to try to send the next message.

There’s currently a 5 second timeout to receive a reply for a message. This is hardcoded, so feel free to change it in the code. Future work is for me to add this as a flag

Running in the background on Linux
```nohup [command] &```
Runs in the background via nohup, it writes to a nohup.out file, which can grow quickly if left unattended

```nohup [command] > file.log &```
Runs in the background via nohup, it writes to a file called “file.log”, which can grow quickly if left unattended

```nohup [command] > /dev/null 2>&1 &```
Runs in the background via nohup and writes no logs

```nohup python3 mllp_spammer.py -host localhost -p 51961 -sps 1 -mode spam > file.log &```
Runs in mllp_spammer.py in the background and writes to file.log in the same folder

```cat /dev/null > nohup.out```
Clears the nohup.out file. You can do this while mllp_spammer is still writing to it

### Terminating background running processes on Linux
```ps -ef | grep python```
Views the running processes for python

```pkill -9 -f mllp_spammer.py```
Closes all running instances of the script, use the script name that is appropriate

```kill [id(s)]```
Terminate one or more processes, separate ids with spaces

# Appendix
To Fix At Some Time:
Combine Non-persistent and persistent versions into 1 with flags for options
Non-persistent - Hardcoded 5 second timeout for socket connection. This means if no reply occurs in 5 seconds it will disconnect. This should be a flag
