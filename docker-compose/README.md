# Instructions to run buildbot using docker-compose

Below you can find instructions on how you can run master-web with docker-compose
locally:

Requirements:

```
* docker
* docker-compose
```

To run buildbot locally with a pre-initialized DB to populate some fields

```bash
git clone https://github.com/MariaDB/buildbot.git
cd buildbot/docker-compose
ln -s config/master-private.cfg-sample config/master-private.cfg
ln -s ../ buildbot
mkdir -p logs db mariadb/tmp
cd db
wget https://ci.mariadb.org/helper_files/buildbot_dump.sql.gz
gzip -d buildbot_dump.sql.gz
cd ..
docker-compose up -d
```

Now, the interface should be up and running at `http://localhost:8010/`
