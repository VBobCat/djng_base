FROM valkey/valkey:trixie

# Instala e atualiza pacotes do SO e dependências
RUN apt-get update && \
    apt-get upgrade -qy && \
    apt-get install -qy locales tzdata &&  \
    rm -rf /var/lib/apt/lists/*

# Localização e horário
RUN localedef -i pt_BR -f UTF-8 pt_BR.UTF-8
ENV LANG=pt_BR.UTF-8
ENV LANGUAGE=pt_BR.UTF-8
ENV LC_ALL=pt_BR.UTF-8
ENV TZ="America/Sao_Paulo"
