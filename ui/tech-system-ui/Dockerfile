FROM node:22-alpine AS build

WORKDIR /app

COPY ui/tech-system-ui/package*.json ./
RUN npm ci

COPY ui/tech-system-ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY ui/tech-system-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
