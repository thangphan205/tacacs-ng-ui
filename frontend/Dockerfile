# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM node:26 AS build-stage

WORKDIR /app

COPY package*.json /app/

RUN npm install

COPY ./ /app/

ARG VITE_API_URL=${VITE_API_URL}
# Build context has no .git; docker-compose.yml passes these in.
ARG GIT_BRANCH=
ARG GIT_COMMIT=

RUN npm run build


# Stage 1, based on Nginx, to have only the compiled app, ready for production with Nginx
FROM nginx:1

COPY --from=build-stage /app/dist/ /usr/share/nginx/html

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
COPY ./nginx-backend-proxy.conf /etc/nginx/extra-conf.d/backend-proxy.conf
