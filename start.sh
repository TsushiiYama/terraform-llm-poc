sudo docker-compose up -d
nohup sudo docker exec terraform-llm-ollama ollama serve &
sudo docker exec terraform-llm-ollama ollama pull codegemma:2b
