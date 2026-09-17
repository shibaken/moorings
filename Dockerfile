# Prepare the base environment.
ARG IMAGE_TAG
ARG IMAGE_NAME
FROM ghcr.io/dbca-wa/docker-apps-dev:ubuntu_2604_base_python_node as builder_base_moorings
ARG IMAGE_TAG
ARG IMAGE_NAME
RUN echo "Building version: $IMAGE_TAG for $IMAGE_NAME"
ENV CONTAINER_IMAGE_TAG=${IMAGE_TAG}
ENV CONTAINER_IMAGE_NAME=${IMAGE_NAME}
MAINTAINER asi@dbca.wa.gov.au
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Australia/Perth
ENV PRODUCTION_EMAIL=True
ENV SECRET_KEY="ThisisNotRealKey"
ENV NODE_MAJOR=22
ENV VIRTUAL_ENV=/app/venv

RUN apt-get clean
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install --no-install-recommends -y curl gnupg wget git libmagic-dev gcc g++ binutils libproj-dev tzdata gpg-agent 
RUN apt update


# Install nodejs
# RUN update-ca-certificates
# RUN mkdir -p /etc/apt/keyrings && \
#     curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
#     echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" \
#     | tee /etc/apt/sources.list.d/nodesource.list && \
#     apt-get update && \
#     apt-get install -y nodejs

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
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN git config --global --add safe.directory /app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN touch /app/git_hash
RUN pip install --no-cache-dir -r requirements.txt

# Install the project (ensure that frontend projects have been built prior to this step).
FROM python_libs_moorings

COPY gunicorn.ini manage_mo.py ./
RUN touch /app/.env
COPY .git ./.git
COPY --chown=oim:oim mooring ./mooring

# Build frontend: this must be done AFTER copying the source code and BEFORE running collectstatic.
RUN echo "--- Building frontend application: admissions ---" && \
    cd "/app/mooring/frontend/admissions" && \
    npm ci && \
    npm run build
RUN echo "--- Building frontend application: availability2 ---" && \
    cd "/app/mooring/frontend/availability2" && \
    npm ci && \
    npm run build
RUN echo "--- Building frontend application: exploreparks ---" && \
    cd "/app/mooring/frontend/exploreparks" && \
    npm ci && \
    npm run build
RUN echo "--- Building frontend application: mooring ---" && \
    cd "/app/mooring/frontend/mooring" && \
    npm ci && \
    npm run build

RUN python manage_mo.py collectstatic --noinput

RUN mkdir /app/tmp/
RUN chmod 777 /app/tmp/

COPY --chown=oim:oim  python-cron ./
COPY --chown=oim:oim startup.sh /
RUN chmod 755 /startup.sh
# cron end

# cleanup
USER root
RUN wget https://raw.githubusercontent.com/dbca-wa/wagov_utils/refs/heads/main/wagov_utils/bin/package_cleanup_2604.sh -O /tmp/package_cleanup_2604.sh
RUN chmod 755 /tmp/package_cleanup_2604.sh
RUN /tmp/package_cleanup_2604.sh
USER oim

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]
