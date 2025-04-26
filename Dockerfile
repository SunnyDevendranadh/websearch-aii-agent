FROM python:3.11-slim

# Install Rust and other dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY market_research_cli/ ./market_research_cli/

# Create reports directory for output
RUN mkdir -p reports

# Build Rust components
RUN cd market_research_cli/market_research_core && \
    maturin develop

# Set environment variables (these will be overridden at runtime)
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV BRAVE_API_KEY=""

# Volume for persistent reports
VOLUME ["/app/reports"]

# Default command (can be overridden)
ENTRYPOINT ["python", "market_research_cli/fast_cli.py"]

# Default to running in interactive mode
CMD []

# Documentation for running the container:
# 
# Building:
# docker build -t market-research-gen .
#
# Running interactively:
# docker run -it --rm \
#   -v "$(pwd)/reports:/app/reports" \
#   -e OPENAI_API_KEY=your_key \
#   -e ANTHROPIC_API_KEY=your_key \
#   market-research-gen
#
# Running in headless mode:
# docker run --rm \
#   -v "$(pwd)/reports:/app/reports" \
#   -e OPENAI_API_KEY=your_key \
#   -e ANTHROPIC_API_KEY=your_key \
#   market-research-gen \
#   --headless --topic "AI in Healthcare" --model claude 