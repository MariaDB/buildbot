# About

 MariaDB Foundation configuration of a Single-Node, Single-Drive MinIO deployment for running server S3 integration tests in BuildBot.

Available at: [minio.mariadb.org](https://minio.mariadb.org)

## Usage

**Docker-compose.yaml** consists of two services:

* **NGINX**, responsible for the SSL termination and the routing to the appropriate locations for the console and the API, see **minio.conf**

* A single node/drive **MinIO** instance configured to expose the **console** and **API** on HTTP ports 8080/8081. The container is bind mounted to a data directory for persistent state (buckets, user configuration, and so on).

**To run it locally**, one can only spin-up the MinIO service and access it on localhost, without any other prerequisites. Without providing the ENV variables ```MINIO_ROOT_{USER,PASSWORD}```, default credentials are used. Please consult the official documentation for more details.

### Service stop/start

```
docker-compose down
docker-compose --env-file .env -d
```

### TLS configuration

LE certificates are provided by **Certbot** with the **Webroot** plugin. This assumes NGINX is configured to handle ACME challenges on port 80.

See [certbot](https://eff-certbot.readthedocs.io/en/stable/using.html) documentation on how to generate/renew certificates.

We need to generate a certificate with 2 SAN's:

1. minio.mariadb.org
1. minio.dev.mariadb.org (for future use)

For certbot, create a **post-hook** that is able to:

1. transfer the renewed certificates to the nginx SSL path (see volume mounts)
1. restart nginx container (via docker-compose)

 Make sure **dhparam** is available for NGINX.

 ```
 curl https://ssl-config.mozilla.org/ffdhe2048.txt > /path/to/dhparam
 ```

### Certificate renewal

On the host, under ```/etc/cron.d``` , replace the contents of the existing certbot file with:

```
0 */12 * * * root perl -e 'sleep int(rand(43200))' && certbot -q renew --post-hook "bash /etc/letsencrypt/post_hook.sh"
```
