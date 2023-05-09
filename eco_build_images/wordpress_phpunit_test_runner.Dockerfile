FROM php:7.4-cli

# https://github.com/WordPress/phpunit-test-runner/blob/master/README.md#0-requirements

# hadolint ignore=DL3008
RUN apt-get update ; \
    apt-get install -y --no-install-recommends \
		git \
		grunt \
		libfreetype6-dev \
		libjpeg62-turbo-dev \
		libpng-dev \
		rsync \
		unzip \
		wget \
	&& docker-php-ext-configure gd --with-freetype --with-jpeg \
	&& docker-php-ext-install -j"$(nproc)" gd mysqli \
        && rm -rf /var/lib/apt/lists/*

# Waiting on upstream PRs #176, 177, with issue #178 as added bonus
RUN git clone --branch all_changes --single-branch --depth 1 https://github.com/grooverdan/phpunit-test-runner.git /phpunit-test-runner

# because of https://github.com/WordPress/wordpress-develop/commit/db0290b04264de1fa791b6973ce3122ccc160a90
ENV NVM_DIR="/root/.nvm"

RUN bash -c "set -o pipefail ; curl -o - https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash; . \"$NVM_DIR/nvm.sh\" && nvm install 14.15.0"

COPY wordpress_phpunit_test_runner.env /phpunit-test-runner/.env
COPY wordpress_phpunit_test_runner.entrypoint /entrypoint.sh

WORKDIR /phpunit-test-runner

ENV COMPOSER_ALLOW_SUPERUSER=1
RUN bash -c 'source /root/.bashrc && source .env && php prepare.php'

ENTRYPOINT ["/entrypoint.sh"]

CMD ["test.php"]
