# Prepare the base environment.
FROM ubuntu:24.04 as builder_base_moorings
MAINTAINER asi@dbca.wa.gov.au
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Australia/Perth
ENV PRODUCTION_EMAIL=True
ENV SECRET_KEY="ThisisNotRealKey"
RUN apt-get clean
RUN apt-get update
RUN apt-get install --no-install-recommends -y software-properties-common
RUN apt-get upgrade -y
RUN apt-get install --no-install-recommends -y wget git libmagic-dev gcc g++ binutils libproj-dev gdal-bin tzdata cron rsyslog gunicorn libreoffice gpg-agent 
RUN apt-get install --no-install-recommends -y libpq-dev patch virtualenv
RUN apt-get install --no-install-recommends -y postgresql-client mtr htop vim ssh
RUN apt-get install --no-install-recommends -y postfix syslog-ng syslog-ng-core
RUN apt update
RUN apt-get install --no-install-recommends -y  python3 python3-dev python3-pip python3-setuptools

RUN groupadd -g 5000 oim 
RUN useradd -g 5000 -u 5000 oim -s /bin/bash -d /app
RUN mkdir /app 
RUN chown -R oim.oim /app 

COPY timezone /etc/timezone
ENV TZ=Australia/Perth
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Default Scripts
RUN wget https://raw.githubusercontent.com/dbca-wa/wagov_utils/main/wagov_utils/bin/default_script_installer.sh -O /tmp/default_script_installer.sh
RUN chmod 755 /tmp/default_script_installer.sh
RUN /tmp/default_script_installer.sh

# Install Python libs from requirements.txt.
FROM builder_base_moorings as python_libs_moorings
WORKDIR /app
USER oim
RUN virtualenv /app/venv
ENV PATH=/app/venv/bin:$PATH
RUN git config --global --add safe.directory /app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN touch /app/git_hash
# RUN pip install --no-cache-dir -r requirements.txt  # <==== Reenable when python install is working

# Install the project (ensure that frontend projects have been built prior to this step).
FROM python_libs_moorings

COPY gunicorn.ini manage_mo.py ./
RUN touch /app/.env
COPY --chown=oim:oim mooring ./mooring
# RUN python manage_mo.py collectstatic --noinput  # <==== Reenable when python install is working

RUN mkdir /app/tmp/
RUN chmod 777 /app/tmp/

COPY --chown=oim:oim startup.sh /
RUN chmod 755 /startup.sh
# cron end

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]
