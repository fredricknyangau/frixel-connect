import paramiko
import sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.56.100', username='admin', password='ZealNet2026')

stdin, stdout, stderr = client.exec_command(" ".join(sys.argv[1:]))
print(stdout.read().decode())
print(stderr.read().decode(), file=sys.stderr)
client.close()
