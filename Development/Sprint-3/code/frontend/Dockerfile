# 1. Use Node image
FROM node:22-alpine

# 2. Set working directory
WORKDIR /app

# 3. Declare the ARG for Next.js
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 4. Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# 5. Copy all source code
COPY . .

# 6. Build app
RUN npm run build

# 7. Expose port
EXPOSE 3000

# 8. Run app
CMD ["npm", "start"]