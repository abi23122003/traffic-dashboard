"""
Fuel price calculation module for route cost analysis.
Provides fuel price data and cost calculation utilities.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Default fuel prices in INR (for India)
DEFAULT_FUEL_PRICES = {
    'petrol': 102.50,  # INR per liter
    'diesel': 94.50,   # INR per liter
    'cng': 75.00,      # INR per kg
    'ev': 8.00         # INR per unit (approx)
}

# Average fuel efficiency (km per liter/unit)
FUEL_EFFICIENCY = {
    'petrol': 15.0,    # km per liter
    'diesel': 18.0,    # km per liter
    'cng': 20.0,       # km per kg
    'ev': 6.0          # km per unit
}

class FuelPriceManager:
    """Manages fuel prices with caching."""
    
    def __init__(self):
        self._prices = DEFAULT_FUEL_PRICES.copy()
        self._last_update = None
        self._cache_duration = timedelta(hours=24)  # Update daily
    
    def get_prices(self, force_refresh: bool = False) -> Dict[str, float]:
        """
        Get current fuel prices.
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            Dictionary of fuel prices
        """
        # Check if we need to update
        if (force_refresh or 
            self._last_update is None or 
            datetime.now() - self._last_update > self._cache_duration):
            self._update_prices()
        
        return self._prices
    
    def _update_prices(self):
        """Update fuel prices from API or fallback to defaults."""
        try:
            # Try to fetch from public API (example using government data)
            # You can replace this with actual API endpoint
            import requests
            response = requests.get(
                "https://api.data.gov.in/resource/...",  # Replace with actual API
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # Parse API response and update prices
                # This is a placeholder - implement based on actual API
                pass
        except Exception as e:
            logger.warning(f"Could not fetch fuel prices from API: {e}")
            # Keep using default prices
        
        self._last_update = datetime.now()

# Global instance
_fuel_manager = FuelPriceManager()

def get_current_fuel_prices(fuel_type: str = 'petrol') -> Dict[str, float]:
    """
    Get current fuel prices.
    
    Args:
        fuel_type: Type of fuel (petrol, diesel, cng, ev)
        
    Returns:
        Dictionary with fuel prices
    """
    return _fuel_manager.get_prices()

def calculate_route_cost_with_fuel(
    distance_km: float,
    travel_time_min: float,
    delay_min: float,
    fuel_type: str = 'petrol',
    time_weight: float = 0.1,      # INR per minute of travel time
    delay_weight: float = 0.05,    # INR per minute of delay
    vehicle_efficiency: Optional[float] = None
) -> float:
    """
    Calculate route cost based on fuel consumption.
    
    Args:
        distance_km: Distance in kilometers
        travel_time_min: Travel time in minutes
        delay_min: Delay in minutes
        fuel_type: Type of fuel (petrol, diesel, cng, ev)
        time_weight: Cost per minute of travel time (opportunity cost)
        delay_weight: Cost per minute of delay (penalty)
        vehicle_efficiency: Custom vehicle efficiency (km per liter/unit)
        
    Returns:
        Total cost in INR
    """
    # Get fuel prices
    prices = get_current_fuel_prices(fuel_type)
    fuel_price = prices.get(fuel_type, DEFAULT_FUEL_PRICES.get(fuel_type, 100))
    
    # Get vehicle efficiency
    if vehicle_efficiency is None:
        efficiency = FUEL_EFFICIENCY.get(fuel_type, 15.0)
    else:
        efficiency = vehicle_efficiency
    
    # Calculate fuel cost
    if efficiency > 0:
        fuel_consumed_liters = distance_km / efficiency
        fuel_cost = fuel_consumed_liters * fuel_price
    else:
        fuel_cost = 0
    
    # Time-based costs (opportunity cost of time)
    time_cost = travel_time_min * time_weight
    
    # Delay penalty (extra cost for being late)
    delay_penalty = delay_min * delay_weight
    
    # Total cost
    total_cost = fuel_cost + time_cost + delay_penalty
    
    return round(total_cost, 2)

def get_route_cost_breakdown(
    distance_km: float,
    travel_time_min: float,
    delay_min: float,
    fuel_type: str = 'petrol'
) -> Dict[str, float]:
    """
    Get detailed breakdown of route costs.
    
    Returns:
        Dictionary with cost breakdown
    """
    fuel_cost = calculate_route_cost_with_fuel(
        distance_km, travel_time_min, delay_min, fuel_type,
        time_weight=0, delay_weight=0  # Only fuel cost
    )
    
    time_cost = calculate_route_cost_with_fuel(
        distance_km, travel_time_min, delay_min, fuel_type,
        time_weight=0.1, delay_weight=0, fuel_cost_only=False
    )
    
    total_cost = calculate_route_cost_with_fuel(
        distance_km, travel_time_min, delay_min, fuel_type
    )
    
    return {
        'fuel_cost': fuel_cost,
        'time_cost': total_cost - fuel_cost - (delay_min * 0.05),
        'delay_penalty': delay_min * 0.05,
        'total_cost': total_cost,
        'distance_km': distance_km,
        'travel_time_min': travel_time_min,
        'delay_min': delay_min
    }