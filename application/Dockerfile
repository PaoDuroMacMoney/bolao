FROM python:3

MAINTAINER Rodrigo & Colodas "bolaodagalera@gmail.com"

RUN apt-get update \
    && apt-get install -qq -y cron \
    && apt-get install -y -qq vim \
    &&  apt-get install -y --no-install-recommends locales

RUN echo "America/Sao_Paulo" > /etc/timezone; dpkg-reconfigure -f noninteractive tzdata
RUN echo 'pt_BR.UTF-8 UTF-8' >> /etc/locale.gen && locale-gen && DEBIAN_FRONTEND=noninteractive dpkg-reconfigure locales

RUN mkdir /bolao
RUN mkdir /bolao/application

WORKDIR bolao/application

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Give execution rights on the cron job
RUN chmod 0644 crawler_cron

RUN chmod 755 ./start.sh

CMD ["./start.sh"]