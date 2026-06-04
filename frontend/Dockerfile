FROM node:20-alpine AS base

# Install yarn
RUN corepack enable && corepack prepare yarn@4.3.1 --activate

WORKDIR /app

# Copy package files
COPY package.json yarn.lock .yarnrc.yml ./

# Install dependencies
RUN yarn install --frozen-lockfile

# Copy source
COPY . .

EXPOSE 5173

CMD ["yarn", "dev", "--host"]
