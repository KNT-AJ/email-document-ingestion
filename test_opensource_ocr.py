#!/usr/bin/env python3
"""Test script for open-source OCR integrations."""

import os
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ocr import (
    PytesseractOCRService,
    PaddleOCRService,
    OpenSourceOCRFactory,
    OpenSourceOCREngine,
    OCRError
)
from services.blob_storage.factory import get_blob_storage
from services.blob_storage.config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)


def create_test_image(text: str, width: int = 400, height: int = 100) -> Path:
    """Create a test image with text for OCR testing."""
    # Create a white image
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Try to use a better font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)  # macOS
        except OSError:
            font = ImageFont.load_default()
    
    # Calculate text position (centered)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # Draw text
    draw.text((x, y), text, fill='black', font=font)
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    image.save(temp_file.name, 'PNG')
    temp_file.close()
    
    return Path(temp_file.name)


def test_pytesseract_service():
    """Test PytesseractOCRService functionality."""
    print("\n=== Testing PytesseractOCRService ===")
    
    try:
        # Initialize storage service
        storage_config = get_config()
        storage_service = get_blob_storage(storage_config)
        
        # Create OCR service
        ocr_service = PytesseractOCRService(storage_service=storage_service)
        
        # Health check
        health = ocr_service.health_check()
        print(f"Health check: {health}")
        
        if health['status'] != 'healthy':
            print("❌ PytesseractOCRService is not healthy")
            return False
        
        # Test with simple text image
        test_text = "Hello World! This is a test."
        test_image_path = create_test_image(test_text)
        
        try:
            # Analyze document
            result = ocr_service.analyze_document(test_image_path)
            
            # Extract and validate results
            extracted_text = ocr_service.extract_text(result)
            metrics = ocr_service.calculate_metrics(result)
            
            print(f"Original text: {test_text}")
            print(f"Extracted text: {extracted_text}")
            print(f"Metrics: {metrics}")
            
            # Check if text extraction worked reasonably well
            if "Hello" in extracted_text and "World" in extracted_text:
                print("✅ PytesseractOCRService text extraction successful")
                return True
            else:
                print("❌ PytesseractOCRService text extraction failed")
                return False
                
        finally:
            # Clean up test image
            os.unlink(test_image_path)
            
    except Exception as e:
        logger.error("PytesseractOCRService test failed", error=str(e))
        print(f"❌ PytesseractOCRService test failed: {e}")
        return False


def test_paddleocr_service():
    """Test PaddleOCRService functionality."""
    print("\n=== Testing PaddleOCRService ===")
    
    try:
        # Initialize storage service
        storage_config = get_config()
        storage_service = get_blob_storage(storage_config)
        
        # Create OCR service
        ocr_service = PaddleOCRService(
            storage_service=storage_service,
            lang='en',
            use_angle_cls=True,
            use_gpu=False,
            show_log=False
        )
        
        # Health check
        health = ocr_service.health_check()
        print(f"Health check: {health}")
        
        if health['status'] != 'healthy':
            print("❌ PaddleOCRService is not healthy")
            return False
        
        # Test with simple text image
        test_text = "PaddleOCR Test 123"
        test_image_path = create_test_image(test_text)
        
        try:
            # Analyze document
            result = ocr_service.analyze_document(test_image_path)
            
            # Extract and validate results
            extracted_text = ocr_service.extract_text(result)
            metrics = ocr_service.calculate_metrics(result)
            
            print(f"Original text: {test_text}")
            print(f"Extracted text: {extracted_text}")
            print(f"Metrics: {metrics}")
            
            # Check if text extraction worked reasonably well
            if "PaddleOCR" in extracted_text or "Test" in extracted_text:
                print("✅ PaddleOCRService text extraction successful")
                return True
            else:
                print("❌ PaddleOCRService text extraction failed")
                return False
                
        finally:
            # Clean up test image
            os.unlink(test_image_path)
            
    except Exception as e:
        logger.error("PaddleOCRService test failed", error=str(e))
        print(f"❌ PaddleOCRService test failed: {e}")
        return False


def test_factory():
    """Test OpenSourceOCRFactory functionality."""
    print("\n=== Testing OpenSourceOCRFactory ===")
    
    try:
        # Get available engines
        available_engines = OpenSourceOCRFactory.get_available_engines()
        print(f"Available engines: {available_engines}")
        
        # Test auto selection
        selected_engine = OpenSourceOCRFactory.auto_select_engine(language='en')
        print(f"Auto-selected engine for English: {selected_engine}")
        
        selected_engine_chinese = OpenSourceOCRFactory.auto_select_engine(language='ch')
        print(f"Auto-selected engine for Chinese: {selected_engine_chinese}")
        
        # Test service creation through factory
        try:
            pytesseract_service = OpenSourceOCRFactory.create_pytesseract_service(language='eng')
            print("✅ Factory created PytesseractOCRService successfully")
        except Exception as e:
            print(f"❌ Factory failed to create PytesseractOCRService: {e}")
            return False
            
        try:
            paddleocr_service = OpenSourceOCRFactory.create_paddleocr_service(lang='en')
            print("✅ Factory created PaddleOCRService successfully")
        except Exception as e:
            print(f"❌ Factory failed to create PaddleOCRService: {e}")
            return False
        
        print("✅ OpenSourceOCRFactory tests passed")
        return True
        
    except Exception as e:
        logger.error("OpenSourceOCRFactory test failed", error=str(e))
        print(f"❌ OpenSourceOCRFactory test failed: {e}")
        return False


def test_multipage_pdf():
    """Test PDF processing capability."""
    print("\n=== Testing PDF Processing ===")
    
    try:
        # Create a simple multi-page PDF test (requires reportlab)
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            # Create test PDF
            pdf_path = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            c = canvas.Canvas(pdf_path.name, pagesize=letter)
            
            # Page 1
            c.drawString(100, 750, "This is page one of the test PDF.")
            c.drawString(100, 730, "It contains some sample text for OCR.")
            c.showPage()
            
            # Page 2
            c.drawString(100, 750, "This is page two.")
            c.drawString(100, 730, "More text for testing.")
            c.showPage()
            
            c.save()
            pdf_path.close()
            
            # Test with PytesseractOCRService
            try:
                pytesseract_service = OpenSourceOCRFactory.create_pytesseract_service()
                result = pytesseract_service.analyze_document(Path(pdf_path.name))
                
                extracted_text = result['text']
                metrics = result['metrics']
                
                print(f"PDF pages processed: {metrics.get('page_count', 0)}")
                print(f"PDF text sample: {extracted_text[:100]}...")
                
                if metrics.get('page_count', 0) >= 2 and len(extracted_text) > 0:
                    print("✅ PDF processing successful")
                    return True
                else:
                    print("❌ PDF processing failed")
                    return False
                    
            finally:
                os.unlink(pdf_path.name)
                
        except ImportError:
            print("⚠️  Skipping PDF test - reportlab not available")
            return True
            
    except Exception as e:
        logger.error("PDF processing test failed", error=str(e))
        print(f"❌ PDF processing test failed: {e}")
        return False


def main():
    """Run all OCR tests."""
    print("🚀 Starting Open-Source OCR Integration Tests")
    
    results = []
    
    # Test individual services
    results.append(("PytesseractOCRService", test_pytesseract_service()))
    results.append(("PaddleOCRService", test_paddleocr_service()))
    results.append(("OpenSourceOCRFactory", test_factory()))
    results.append(("PDF Processing", test_multipage_pdf()))
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, passed_test in results:
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name:<25} {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
