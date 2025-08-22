"""Date and time utility functions for the Email & Document Ingestion System."""

import re
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
import typer


def parse_date_range(start_date: str, end_date: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    Parse start and end dates into datetime objects.
    
    Args:
        start_date: Start date string in various formats
        end_date: End date string (optional, defaults to now)
        
    Returns:
        Tuple of (start_datetime, end_datetime) with timezone info
        
    Raises:
        ValueError: If date parsing fails
    """
    try:
        # Parse start date
        start_dt = parse_date_string(start_date)
        
        # Parse end date or default to now
        if end_date:
            end_dt = parse_date_string(end_date)
        else:
            end_dt = datetime.now(timezone.utc)
            
        return start_dt, end_dt
        
    except Exception as e:
        raise ValueError(f"Error parsing date range: {e}")


def parse_date_string(date_str: str) -> datetime:
    """
    Parse a date string into a datetime object with various format support.
    
    Supported formats:
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM:SS
    - YYYY-MM-DD HH:MM
    - ISO format with timezone
    - Relative dates like "7 days ago", "1 week ago", "30 days ago"
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object with timezone info
        
    Raises:
        ValueError: If date format is not recognized
    """
    date_str = date_str.strip()
    
    # Handle relative dates
    relative_match = re.match(r'^(\d+)\s+(days?|weeks?|months?)\s+ago$', date_str.lower())
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2).rstrip('s')  # Remove plural 's'
        
        now = datetime.now(timezone.utc)
        if unit == 'day':
            return now - timedelta(days=amount)
        elif unit == 'week':
            return now - timedelta(weeks=amount)
        elif unit == 'month':
            # Approximate month as 30 days
            return now - timedelta(days=amount * 30)
    
    # Common date formats to try
    formats = [
        '%Y-%m-%d %H:%M:%S',      # 2024-01-01 12:30:45
        '%Y-%m-%d %H:%M',         # 2024-01-01 12:30
        '%Y-%m-%d',               # 2024-01-01
        '%Y/%m/%d %H:%M:%S',      # 2024/01/01 12:30:45
        '%Y/%m/%d %H:%M',         # 2024/01/01 12:30
        '%Y/%m/%d',               # 2024/01/01
        '%m/%d/%Y %H:%M:%S',      # 01/01/2024 12:30:45
        '%m/%d/%Y %H:%M',         # 01/01/2024 12:30
        '%m/%d/%Y',               # 01/01/2024
        '%d-%m-%Y %H:%M:%S',      # 01-01-2024 12:30:45
        '%d-%m-%Y %H:%M',         # 01-01-2024 12:30
        '%d-%m-%Y',               # 01-01-2024
    ]
    
    # Try each format
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Add timezone if not present
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    # Try ISO format with timezone
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass
    
    raise ValueError(f"Unable to parse date string: '{date_str}'. "
                    "Supported formats: YYYY-MM-DD, YYYY-MM-DD HH:MM:SS, "
                    "ISO format, or relative like '30 days ago'")


def validate_date_range(start_dt: datetime, end_dt: datetime, max_messages: int = 1000) -> None:
    """
    Validate a date range for backfill operations.
    
    Args:
        start_dt: Start datetime
        end_dt: End datetime  
        max_messages: Maximum messages allowed for the range
        
    Raises:
        ValueError: If validation fails
    """
    # Check that start is before end
    if start_dt >= end_dt:
        raise ValueError("Start date must be before end date")
    
    # Check that dates are not too far in the future
    now = datetime.now(timezone.utc)
    if start_dt > now:
        raise ValueError("Start date cannot be in the future")
    if end_dt > now + timedelta(days=1):
        raise ValueError("End date cannot be more than 1 day in the future")
    
    # Check range is not too large (to prevent overwhelming the system)
    duration = end_dt - start_dt
    
    # Warn about large ranges
    if duration > timedelta(days=365):
        typer.echo(f"⚠️  Warning: Large date range ({duration.days} days)")
        if not typer.confirm("This may process a very large number of emails. Continue?"):
            raise ValueError("Operation cancelled by user")
    
    # Estimate potential messages and warn if needed
    if duration > timedelta(days=30) and max_messages > 5000:
        typer.echo(f"⚠️  Warning: Large range ({duration.days} days) with high message limit ({max_messages})")
        if not typer.confirm("This may take a very long time. Continue?"):
            raise ValueError("Operation cancelled by user")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds into human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def get_gmail_date_query(start_dt: datetime, end_dt: datetime) -> str:
    """
    Convert datetime range to Gmail API query format.
    
    Gmail uses dates in YYYY/MM/DD format for queries.
    
    Args:
        start_dt: Start datetime
        end_dt: End datetime
        
    Returns:
        Gmail query string for the date range
    """
    start_date = start_dt.strftime('%Y/%m/%d')
    end_date = end_dt.strftime('%Y/%m/%d')
    
    # Gmail query uses "after" and "before" operators
    return f"after:{start_date} before:{end_date}"


def get_relative_date(days_ago: int) -> datetime:
    """
    Get a datetime object for a number of days ago.
    
    Args:
        days_ago: Number of days in the past
        
    Returns:
        datetime object with timezone info
    """
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def is_recent_date(dt: datetime, max_age_days: int = 7) -> bool:
    """
    Check if a datetime is recent (within max_age_days).
    
    Args:
        dt: Datetime to check
        max_age_days: Maximum age in days to consider recent
        
    Returns:
        True if the date is recent, False otherwise
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    age = datetime.now(timezone.utc) - dt
    return age.total_seconds() <= max_age_days * 24 * 3600


# Common date constants
COMMON_RANGES = {
    'today': lambda: (get_relative_date(1), datetime.now(timezone.utc)),
    'yesterday': lambda: (get_relative_date(2), get_relative_date(1)),
    'last_week': lambda: (get_relative_date(7), datetime.now(timezone.utc)),
    'last_month': lambda: (get_relative_date(30), datetime.now(timezone.utc)),
    'last_3_months': lambda: (get_relative_date(90), datetime.now(timezone.utc)),
    'last_year': lambda: (get_relative_date(365), datetime.now(timezone.utc)),
}


def get_common_range(range_name: str) -> Tuple[datetime, datetime]:
    """
    Get a common date range by name.
    
    Args:
        range_name: Name of the range ('today', 'last_week', etc.)
        
    Returns:
        Tuple of (start_datetime, end_datetime)
        
    Raises:
        ValueError: If range name is not recognized
    """
    if range_name not in COMMON_RANGES:
        available = ', '.join(COMMON_RANGES.keys())
        raise ValueError(f"Unknown range '{range_name}'. Available: {available}")
    
    return COMMON_RANGES[range_name]()
