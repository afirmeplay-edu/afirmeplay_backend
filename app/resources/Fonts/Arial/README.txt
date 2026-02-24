Fontes para geração de PDF (relatórios) - padronização entre Windows e Linux.

Coloque aqui os arquivos de fonte para o WeasyPrint usar o mesmo tipo de letra
em todos os ambientes (evita tabelas desalinhadas e texto mais "negrito" no servidor):

  - arial.ttf       (Arial normal)
  - arialbd.ttf     (Arial bold / negrito)

Nomes alternativos aceitos pelo código em formularios.py (opcional):
  Arial.ttf, ARIAL.TTF, Arial-Bold.ttf, ARIALBD.TTF, etc.

Se os arquivos não existirem, o sistema usa a fonte padrão do ambiente
(sans-serif), o que pode causar diferenças de layout entre local e produção.

No Docker, COPY . . já inclui app/resources; basta ter os .ttf nesta pasta
antes do build (ou montar o volume em produção).
