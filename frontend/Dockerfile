FROM node:20-alpine AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:20-alpine
WORKDIR /web
COPY --from=build /web ./
EXPOSE 3000
CMD ["npm", "run", "start"]
