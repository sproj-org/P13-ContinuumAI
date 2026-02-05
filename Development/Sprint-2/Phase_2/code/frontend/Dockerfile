# 1. Use Node image
FROM node:22-alpine

# 2. Set working directory
WORKDIR /app

#Declare the ARG
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# 3. Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# 4. Copy all source code
COPY . .

# 5. Build app
RUN npm run build

# 6. Expose port
EXPOSE 3000

# 7. Run app
CMD ["npm", "start"]
