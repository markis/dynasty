# Dynasty Fantasy Football Dashboard

A comprehensive Streamlit web application for analyzing fantasy football dynasty leagues, providing real-time player valuations, roster analysis, and strategic insights.

## Features

### 🏈 League Analysis
- **Multi-Platform Integration**: Connect to Sleeper leagues with username lookup
- **Real-time Roster Analysis**: View detailed team compositions and values
- **Positional Breakdowns**: Analyze team strength by position (QB, RB, WR, TE)
- **Draft Pick Integration**: Include draft picks in team valuations

### 📊 Player Valuations
- **Multiple Ranking Sources**: 
  - KeepTradeCut
  - DynastyProcess  
  - FantasyCalc
  - FantasyNavigator
- **Historical Trends**: Track player value changes over customizable time periods
- **Linear Regression Analysis**: Identify trending players with statistical analysis

### 🔍 Advanced Features
- **Free Agent Analysis**: Discover undervalued available players
- **IR Stash Recommendations**: Find valuable injured players to stash
- **Interactive Visualizations**: Plotly charts for team comparisons
- **Starter-Only Views**: Focus analysis on starting lineups
- **LLM Integration**: AI-powered insights and recommendations

### 📈 Data Visualization
- **Team Value Charts**: Compare total roster values across league
- **Positional Stacking**: Visual breakdown of team composition
- **Trend Analysis**: Historical value charts for all players
- **Expandable Rosters**: Detailed player-by-player team views

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Sleeper account (for league data)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd dynasty
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
export PSQL_URL="postgresql://username:password@localhost:5432/dynasty"
```

4. **Run the application**
```bash
streamlit run home.py
```

## Docker Setup

### Using Docker Compose
```bash
docker-compose up -d
```

### Manual Docker Build
```bash
docker build -t dynasty-dashboard .
docker run -p 8501:8501 -e PSQL_URL="your-db-url" dynasty-dashboard
```

## Configuration

### Environment Variables
- `PSQL_URL`: PostgreSQL connection string (required)

### Database Setup
The application requires a PostgreSQL database with player rankings data. The database schema is managed through SQLModel.

### Data Sources
Player rankings are pulled from multiple sources and stored in the database with historical tracking for trend analysis.

## Usage

1. **Access the Dashboard**: Navigate to `http://localhost:8501`

2. **Enter Sleeper Username**: Input your Sleeper username in the sidebar

3. **Select League**: Choose from your available leagues

4. **Configure Analysis**:
   - Choose ranking source (KeepTradeCut, DynastyProcess, etc.)
   - Toggle starters-only view
   - Include/exclude draft picks
   - Set trending analysis timeframe

5. **Analyze Results**:
   - View team value comparisons
   - Explore individual rosters
   - Check free agent recommendations
   - Review IR stash opportunities

## Project Structure

```
dynasty/
├── dynasty/                 # Core application package
│   ├── models.py           # Database models
│   ├── db.py              # Database utilities
│   ├── service/           # External API integrations
│   │   ├── sleeper.py     # Sleeper API client
│   │   ├── keeptradecut.py # KeepTradeCut integration
│   │   └── ...            # Other fantasy platforms
│   └── util.py            # Utility functions
├── data/                   # CSV data files
├── tests/                  # Test suite
├── home.py                # Main Streamlit application
├── compose.yml            # Docker Compose configuration
├── Containerfile          # Docker build file
└── requirements.txt       # Python dependencies
```

## Data Import

The application includes import utilities for pulling data from various fantasy football platforms:

```bash
python -m dynasty.import
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Style
The project follows Python best practices with type hints and modern Python features.

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## API Integrations

- **Sleeper API**: League and roster data
- **KeepTradeCut**: Player valuations and trends
- **DynastyProcess**: Advanced dynasty rankings
- **FantasyCalc**: Trade calculator integration
- **FantasyNavigator**: Additional ranking source

## Performance Features

- **Caching**: Streamlit caching for improved performance
- **Database Optimization**: Efficient queries with SQLModel
- **Containerization**: Docker support for easy deployment

## Troubleshooting

### Common Issues

**Database Connection Issues**
- Ensure `PSQL_URL` is properly set
- Verify database is accessible and running

**Sleeper API Errors**  
- Check username spelling
- Verify league access permissions

**Missing Player Data**
- Run data import: `python -m dynasty.import`
- Check ranking source availability

## License

See LICENSE.txt for details.

## Support

For issues and feature requests, please open a GitHub issue with detailed information about your setup and the problem encountered.
