
# INSTALL HASHICORP VAULT
# USAGE: vault server -dev > /dev/null 2>&1 &

RUN curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list \
&& apt-get update \
&& apt-get -y install --no-install-recommends vault \
&& setcap cap_ipc_lock=-ep "$(readlink -f "$(which vault)")" \
&& apt-get clean

# VAULT CONFIGURATION
ENV VAULT_DEV_ROOT_TOKEN_ID='MTR'
# MTR CONFIGURATION
ENV VAULT_TOKEN='MTR'
ENV VAULT_ADDR='http://127.0.0.1:8200'
