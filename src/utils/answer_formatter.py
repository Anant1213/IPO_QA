"""
Answer Formatter - Convert structured KG data to natural language
"""

import json
from typing import Any, Dict


class AnswerFormatter:
    """Converts structured knowledge graph outputs to natural language answers"""
    
    def format(self, raw_output: Any, question: str) -> str:
        """Main formatting method"""
        
        # Handle different output types
        if isinstance(raw_output, dict):
            return self._format_dict(raw_output, question)
        elif isinstance(raw_output, list):
            return self._format_list(raw_output)
        else:
            return str(raw_output)
    
    def _format_dict(self, data: Dict, question: str) -> str:
        """Convert dictionary to natural language based on question context"""
        
        question_lower = question.lower()
        
        # Compensation/Money queries
        if "compensation" in question_lower or "salary" in question_lower:
            return self._format_compensation(data)
        
        # Date queries
        if "when" in question_lower or "date" in question_lower:
            return self._format_date(data)
        
        # Address queries
        if "address" in question_lower:
            return self._format_address(data)
        
        # Director/People lists
        if "directors" in question_lower or "who are" in question_lower:
            return self._format_list_of_people(data)
        
        # Count queries
        if "how many" in question_lower:
            return self._format_count(data)
        
        # Comparison queries
        if "highest" in question_lower or "lowest" in question_lower or "most" in question_lower:
            return self._format_comparison(data, question_lower)
        
        # Default: Try to extract key-value pairs intelligently
        return self._format_generic_dict(data)
    
    def _format_compensation(self, data: Dict) -> str:
        """Format compensation data"""
        if isinstance(data, dict):
            # Multi-year compensation
            if all(k.isdigit() or k in ['2020', '2021', '2022'] for k in data.keys()):
                parts = [f"₹{v:,} million in {k}" for k, v in sorted(data.items())]
                return f"The compensation was {', '.join(parts)}."
            
            # Single value with currency
            if 'value' in data:
                return f"The compensation is ₹{data['value']:,} {data.get('unit', 'million')}."
        
        return f"The compensation is {data}."
    
    def _format_date(self, data: Dict) -> str:
        """Format date information"""
        if isinstance(data, dict):
            if 'date_of_incorporation' in data:
                return f"It was incorporated on {data['date_of_incorporation']}."
            if 'date' in data:
                return f"The date is {data['date']}."
        
        # Fallback to first value that looks like a date
        for key, value in data.items():
            if 'date' in key.lower() and value:
                return f"The {key.replace('_', ' ')} is {value}."
        
        return str(data)
    
    def _format_address(self, data: Dict) -> str:
        """Format address information"""
        if isinstance(data, dict):
            if 'address' in data and data['address']:
                return f"The registered address is: {data['address']}"
            
            # Build address from components
            parts = []
            for key in ['street', 'city', 'state', 'country', 'zip']:
                if key in data and data[key]:
                    parts.append(data[key])
            
            if parts:
                return f"The address is: {', '.join(parts)}"
        
        return "The address information is not available."
    
    def _format_list_of_people(self, data: Dict) -> str:
        """Format list of directors or people"""
        if isinstance(data, dict):
            people = []
            
            # Extract names from dict keys or values
            for key, value in data.items():
                if key and key != 'None':
                    # Check if it's a person name (starts with title)
                    if any(title in key for title in ['Mr.', 'Ms.', 'Dr.', 'Mrs.']):
                        people.append(key)
            
            if people:
                if len(people) == 1:
                    return f"The director is {people[0]}."
                else:
                    return f"The directors include: {', '.join(people)}."
        
        return str(data)
    
    def _format_count(self, data: Dict) -> str:
        """Format count/aggregation queries"""
        if isinstance(data, dict):
            if 'count' in data:
                return f"There are {data['count']}."
            
            # Count dict entries
            count = len([k for k, v in data.items() if v])
            return f"There are {count}."
        
        return str(data)
    
    def _format_comparison(self, data: Dict, question: str) -> str:
        """Format comparison results"""
        if isinstance(data, dict):
            # Find max/min value
            if "highest" in question or "most" in question:
                if data:
                    max_key = max(data.keys(), key=lambda k: data[k] if isinstance(data[k], (int, float)) else 0)
                    return f"The highest is {max_key} with {data[max_key]}."
            elif "lowest" in question:
                if data:
                    min_key = min(data.keys(), key=lambda k: data[k] if isinstance(data[k], (int, float)) else 0)
                    return f"The lowest is {min_key} with {data[min_key]}."
        
        return str(data)
    
    def _format_generic_dict(self, data: Dict) -> str:
        """Generic formatting for any dictionary"""
        if not data:
            return "No information available."
        
        # Single key-value
        if len(data) == 1:
            key, value = list(data.items())[0]
            if value:
                return f"{key.replace('_', ' ').title()}: {value}"
            else:
                return f"{key.replace('_', ' ').title()}"
        
        # Multiple key-values - format as readable text
        parts = []
        for key, value in data.items():
            if value and value != 'None':
                parts.append(f"{key.replace('_', ' ')}: {value}")
        
        if parts:
            return ". ".join(parts) + "."
        
        return "Information not available."
    
    def _format_list(self, data: list) -> str:
        """Format list outputs"""
        if not data:
            return "No items found."
        
        if len(data) == 1:
            return str(data[0])
        
        return ", ".join(str(item) for item in data) + "."
