#!/bin/bash
dnf install git nginx python3.14 python3.14-pip -y 
python3.14 -m pip install notebook boto3 strands-agents bedrock-agentcore mcp

mkdir -p /home/ec2-user/.jupyter
cat > /home/ec2-user/.jupyter/jupyter_notebook_config.py << 'EOF'
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False
c.NotebookApp.password = ''
c.NotebookApp.token = 'smileshark-token'
EOF

chown -R ec2-user:ec2-user /home/ec2-user/.jupyter

cat > /etc/systemd/system/jupyter.service << 'EOF'
[Unit]
Description=Jupyter Notebook
After=network.target

[Service]
Type=simple
User=ec2-user
ExecStart=/usr/bin/python3.14 -m jupyter notebook --no-browser --ip=0.0.0.0 --port=8888
WorkingDirectory=/home/ec2-user
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now jupyter

# 워크숍 코드 다운로드
cd /home/ec2-user
git clone https://github.com/yoonhyunchan/agentic-ai-workshop.git
chown -R ec2-user:ec2-user /home/ec2-user/agentic-ai-workshop

cat > /etc/nginx/conf.d/jupyter.conf << 'EOF'
server {
  listen 80;

  location / {
    proxy_pass http://localhost:8888;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
EOF

systemctl enable --now nginx
