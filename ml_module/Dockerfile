FROM tensorflow/tensorflow:2.0.0b1-py3
EXPOSE 9000
WORKDIR /opt/wsgi

RUN apt-get update && \
    apt install -y bash nano build-essential && \
    useradd --create-home --shell /bin/bash --user-group uwsgi

COPY ./requirements.txt /opt/wsgi/
RUN pip3 install --no-cache-dir -r /opt/wsgi/requirements.txt

COPY ./*py ./wsgi.conf ./*.h5 ./*pickle ./*csv /opt/wsgi/

#RUN cd /opt/wsgi && chown -R uwsgi:uwsgi .

USER uwsgi
CMD [ "uwsgi", "--ini", "/opt/wsgi/wsgi.conf" ]
