FROM node:22-alpine AS build

WORKDIR /app

COPY its/ui/ga-ui/package*.json ./
RUN npm ci

COPY its/ui/ga-ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY its/ui/ga-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

