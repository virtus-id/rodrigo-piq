# Frontend do PIQ: build do React (Vite) servido por Nginx, que também
# repassa as rotas da API para o backend (mesma origem, cookie de sessão funciona).
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
