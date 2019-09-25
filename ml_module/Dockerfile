FROM tensorflow/tensorflow:2.0.0b1-py3
EXPOSE 9000
WORKDIR /opt/wsgi

RUN apt-get update && \
    apt install -y bash nano build-essential openjdk-8-jre-headless && \
    useradd --create-home --shell /bin/bash --user-group uwsgi && \
    echo -n >  /etc/java-8-openjdk/accessibility.properties

COPY ./binary/MarvinBeans /opt/wsgi/MarvinBeans

COPY ./requirements.txt /opt/wsgi/
RUN pip3 install --no-cache-dir -r /opt/wsgi/requirements.txt

COPY ./*py ./wsgi.conf ./*.h5 ./*pickle ./*csv /opt/wsgi/

RUN cd /opt/ && chown -R uwsgi:uwsgi wsgi

USER uwsgi
CMD [ "uwsgi", "--ini", "/opt/wsgi/wsgi.conf" ]
