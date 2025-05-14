sudo docker-compose up -d
sudo docker-compose ps
nohup sudo docker exec terraform-llm-ollama ollama serve
sudo docker exec terraform-llm-ollama ollama pull codegemma:2b
