import logging
import uvicorn
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

from app.api.http import app

# Criar diretório de logs se não existir
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# Configuração central de logging
log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Configurar root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Handler para console (mantém saída no terminal)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format, date_format))

# Handler para arquivo com rotação (máximo 10MB por arquivo, mantém 5 backups)
log_file = os.path.join(log_dir, "app.log")
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format, date_format))

# Adicionar handlers
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Log inicial
logging.info(f"Logging configurado. Arquivo de log: {log_file}")
logging.info(f"Aplicação iniciada em {datetime.now().strftime(date_format)}")

if __name__ == "__main__":
    # Em produção, quem sobe isso é o process manager (systemd, docker, etc.)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

