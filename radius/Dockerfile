FROM freeradius/freeradius-server:latest

# Install postgresql driver for freeradius
RUN apt-get update && \
    apt-get install -y freeradius-postgresql && \
    rm -rf /var/lib/apt/lists/*
