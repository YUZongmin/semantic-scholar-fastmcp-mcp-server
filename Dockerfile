# Generated by https://smithery.ai. See: https://smithery.ai/docs/config#dockerfile
# Start from a base Python image
FROM python:3.8-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server script into the container
COPY semantic_scholar_server.py /app/semantic_scholar_server.py

# Expose the port that the MCP server will run on
EXPOSE 8000

# Set the environment variable for the API key (if available)
# Replace 'your-api-key' with your actual API key if needed
ENV SEMANTIC_SCHOLAR_API_KEY=your-api-key

# Command to run the server
CMD ["python", "semantic_scholar_server.py"]