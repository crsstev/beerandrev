#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== BEER & REVOLUTION - PRODUCTION DEPLOYMENT ===${NC}\n"

echo -e "${RED}WARNING: This will replace the production website!${NC}"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 1
fi

echo -e "\n${YELLOW}Step 1: Backing up current production...${NC}"
BACKUP_DIR="/var/www/beerandrevolution.net.backup.$(date +%Y%m%d_%H%M%S)"
sudo cp -r /var/www/beerandrevolution.net "$BACKUP_DIR"
echo -e "${GREEN}Backup created${NC}\n"

echo -e "${YELLOW}Step 2: Preserving production .env...${NC}"
sudo cp /var/www/beerandrevolution.net/.env /tmp/prod.env.backup
echo -e "${GREEN}.env backed up${NC}\n"

echo -e "${YELLOW}Step 3: Moving code to production...${NC}"
sudo rm -rf /var/www/beerandrevolution.net.old
sudo cp -r /var/www/django/beerandrevolution /var/www/beerandrevolution.net.new
sudo mv /var/www/beerandrevolution.net /var/www/beerandrevolution.net.old
sudo mv /var/www/beerandrevolution.net.new /var/www/beerandrevolution.net
echo -e "${GREEN}Code updated${NC}\n"

echo -e "${YELLOW}Step 4: Restoring production .env...${NC}"
sudo cp /tmp/prod.env.backup /var/www/beerandrevolution.net/.env
echo -e "${GREEN}.env restored${NC}\n"

echo -e "${YELLOW}Step 5: Updating docker-compose for production...${NC}"
sudo sed -i 's/beerandrevolution_web_dev/beerandrevolution_web_prod/g' /var/www/beerandrevolution.net/docker-compose.yml
sudo sed -i 's/beerandrevolution_bot/beerandrevolution_bot_prod/g' /var/www/beerandrevolution.net/docker-compose.yml
sudo sed -i 's/"8001:8001"/"8002:8001"/g' /var/www/beerandrevolution.net/docker-compose.yml
echo -e "${GREEN}Docker compose updated${NC}\n"

echo -e "${YELLOW}Step 6: Updating nginx...${NC}"
sudo tee /etc/nginx/sites-enabled/beerandrevolution.net > /dev/null << 'NGINX'
upstream django {
    server 127.0.0.1:8002;
}

server {
    server_name beerandrevolution.net www.beerandrevolution.net;
    root /var/www/beerandrevolution.net/;
    client_max_body_size 100M;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location /static/ {
        alias /var/www/beerandrevolution.net/app/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /var/www/beerandrevolution.net/app/media/;
    }

    location = /favicon.ico { log_not_found off; access_log off; }
    location = /robots.txt { log_not_found off; access_log off; allow all; }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/amp.beerandrevolution.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/amp.beerandrevolution.net/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = beerandrevolution.net) { return 301 https://$host$request_uri; }
    if ($host = www.beerandrevolution.net) { return 301 https://$host$request_uri; }
    listen 80;
    server_name beerandrevolution.net www.beerandrevolution.net;
    return 404;
}
NGINX

echo -e "${GREEN}Nginx configured${NC}\n"

echo -e "${YELLOW}Step 7: Testing nginx...${NC}"
if sudo nginx -t > /dev/null 2>&1; then
    echo -e "${GREEN}Nginx OK${NC}\n"
else
    echo -e "${RED}Nginx error!${NC}"
    sudo mv /var/www/beerandrevolution.net.old /var/www/beerandrevolution.net
    exit 1
fi

echo -e "${YELLOW}Step 8: Reloading nginx...${NC}"
sudo systemctl reload nginx
echo -e "${GREEN}Nginx reloaded${NC}\n"

echo -e "${YELLOW}Step 9: Restarting Docker containers...${NC}"
sudo docker-compose -f /var/www/beerandrevolution.net/docker-compose.yml down
sudo docker-compose -f /var/www/beerandrevolution.net/docker-compose.yml up -d
sleep 10
echo -e "${GREEN}Containers running${NC}\n"

echo -e "${YELLOW}Step 10: Verifying deployment...${NC}"
if curl -s -I https://beerandrevolution.net | grep -q "200\|301\|302"; then
    echo -e "${GREEN}Website responding${NC}\n"
else
    echo -e "${RED}Website not responding${NC}"
    exit 1
fi

echo -e "${GREEN}=== DEPLOYMENT COMPLETE ===${NC}"
echo -e "${GREEN}Production: https://beerandrevolution.net${NC}"
echo -e "${GREEN}Backup: $BACKUP_DIR${NC}\n"
