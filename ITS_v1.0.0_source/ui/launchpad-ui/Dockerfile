FROM node:22-alpine AS build

WORKDIR /app

COPY ui/launchpad-ui/package*.json ./
RUN npm ci

COPY ui/launchpad-ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY ui/launchpad-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
