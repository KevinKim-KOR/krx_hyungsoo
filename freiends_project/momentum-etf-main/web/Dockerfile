FROM node:24-alpine

WORKDIR /app

COPY web/package.json web/package-lock.json* ./
RUN npm install

COPY shared /shared
COPY web .

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
