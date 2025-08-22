"""
Comprehensive tests for the admin CLI commands implemented in task 23.

This test suite validates all the admin CLI commands:
- labels: list, ensure, assign
- watch: start, stop, status  
- metrics: dump, summary
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner
from cli import app, labels_app, watch_app, metrics_app


runner = CliRunner()


class TestLabelsCommands:
    """Test Gmail label management CLI commands."""
    
    @patch('cli.get_gmail_service')
    def test_labels_list_success(self, mock_get_service):
        """Test successful label listing."""
        # Mock service
        mock_service = Mock()
        mock_service.list_labels.return_value = [
            {'id': 'Label_1', 'name': 'Important', 'type': 'user'},
            {'id': 'Label_2', 'name': 'Work', 'type': 'user'},
            {'id': 'INBOX', 'name': 'INBOX', 'type': 'system'}
        ]
        mock_get_service.return_value = mock_service
        
        # Test command
        result = runner.invoke(app, ['labels', 'list', 'user123'])
        
        assert result.exit_code == 0
        assert 'Important' in result.stdout
        assert 'Work' in result.stdout
        assert 'INBOX' in result.stdout
        assert 'Total: 3 labels' in result.stdout
        
        mock_service.list_labels.assert_called_once_with('user123')
    
    @patch('cli.get_gmail_service')
    def test_labels_list_json_format(self, mock_get_service):
        """Test label listing with JSON format."""
        mock_service = Mock()
        mock_service.list_labels.return_value = [
            {'id': 'Label_1', 'name': 'Important', 'type': 'user'}
        ]
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, ['labels', 'list', 'user123', '--format', 'json'])
        
        assert result.exit_code == 0
        assert '"name": "Important"' in result.stdout
    
    @patch('cli.get_gmail_service')
    def test_labels_list_failure(self, mock_get_service):
        """Test label listing failure."""
        mock_service = Mock()
        mock_service.list_labels.return_value = None
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, ['labels', 'list', 'user123'])
        
        assert result.exit_code == 1
        assert 'Failed to retrieve labels' in result.stdout
    
    @patch('cli.get_gmail_service')
    def test_labels_ensure_success(self, mock_get_service):
        """Test successful label creation/ensuring."""
        mock_service = Mock()
        mock_service.ensure_label_exists.return_value = {
            'id': 'Label_New',
            'name': 'TestLabel',
            'type': 'user'
        }
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, ['labels', 'ensure', 'user123', 'TestLabel'])
        
        assert result.exit_code == 0
        assert 'Label \'TestLabel\' is ready!' in result.stdout
        
        mock_service.ensure_label_exists.assert_called_once_with('user123', 'TestLabel', None)
    
    @patch('cli.get_gmail_service')
    def test_labels_ensure_with_colors(self, mock_get_service):
        """Test label creation with custom colors."""
        mock_service = Mock()
        mock_service.ensure_label_exists.return_value = {
            'id': 'Label_New',
            'name': 'TestLabel',
            'type': 'user',
            'color': {'backgroundColor': '#ff0000', 'textColor': '#ffffff'}
        }
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, [
            'labels', 'ensure', 'user123', 'TestLabel',
            '--bg-color', '#ff0000', '--text-color', '#ffffff'
        ])
        
        assert result.exit_code == 0
        assert 'Background Color: #ff0000' in result.stdout
    
    def test_labels_ensure_invalid_color(self):
        """Test label creation with invalid color format."""
        result = runner.invoke(app, [
            'labels', 'ensure', 'user123', 'TestLabel',
            '--bg-color', 'red'  # Invalid format
        ])
        
        assert result.exit_code == 1
        assert 'bg-color must be in hex format' in result.stdout
    
    @patch('cli.get_gmail_service')
    @patch('cli.typer.confirm')
    def test_labels_assign_success(self, mock_confirm, mock_get_service):
        """Test successful label assignment."""
        mock_confirm.return_value = True
        mock_service = Mock()
        mock_service.assign_labels_to_messages.return_value = {
            'successful': 2,
            'failed': 0,
            'errors': []
        }
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, [
            'labels', 'assign', 'user123', 'msg1,msg2', 'Important,Work'
        ])
        
        assert result.exit_code == 0
        assert 'Successful operations: 2' in result.stdout
    
    @patch('cli.get_gmail_service')
    def test_labels_assign_dry_run(self, mock_get_service):
        """Test label assignment dry run."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, [
            'labels', 'assign', 'user123', 'msg1,msg2', 'Important',
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        assert 'DRY RUN MODE' in result.stdout
        assert 'Would process message 1: msg1' in result.stdout
        # Should not call the actual service
        mock_service.assign_labels_to_messages.assert_not_called()


class TestWatchCommands:
    """Test Gmail watch CLI commands."""
    
    @patch('cli.get_gmail_service')
    @patch('cli.get_gmail_watch_config')
    @patch('cli.typer.confirm')
    @patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': 'test-project'})
    def test_watch_start_success(self, mock_confirm, mock_get_config, mock_get_service):
        """Test successful Gmail watch start."""
        mock_confirm.return_value = True
        
        # Mock services
        mock_service = Mock()
        mock_service.setup_watch_with_retry.return_value = {
            'historyId': '12345',
            'expiration': '1640995200000'
        }
        mock_get_service.return_value = mock_service
        
        mock_config = Mock()
        mock_config.project_id = 'test-project'
        mock_config.create_topic.return_value = 'projects/test-project/topics/gmail-notifications'
        mock_config.grant_gmail_publisher_role.return_value = True
        mock_config.validate_topic_permissions.return_value = {'gmail_has_publisher_role': True}
        mock_get_config.return_value = mock_config
        
        result = runner.invoke(app, ['watch', 'start', 'user123'])
        
        assert result.exit_code == 0
        assert 'Gmail watch started successfully!' in result.stdout
        assert 'History ID: 12345' in result.stdout
    
    @patch('cli.get_gmail_service')
    @patch('cli.typer.confirm')
    def test_watch_stop_success(self, mock_confirm, mock_get_service):
        """Test successful Gmail watch stop."""
        mock_confirm.return_value = True
        
        mock_service = Mock()
        mock_service.stop_watch.return_value = True
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, ['watch', 'stop', 'user123'])
        
        assert result.exit_code == 0
        assert 'Gmail watch stopped successfully!' in result.stdout
        
        mock_service.stop_watch.assert_called_once_with('user123')
    
    @patch('cli.get_gmail_service')
    def test_watch_stop_with_confirm_flag(self, mock_get_service):
        """Test Gmail watch stop with --confirm flag."""
        mock_service = Mock()
        mock_service.stop_watch.return_value = True
        mock_get_service.return_value = mock_service
        
        result = runner.invoke(app, ['watch', 'stop', 'user123', '--confirm'])
        
        assert result.exit_code == 0
        assert 'Gmail watch stopped successfully!' in result.stdout
    
    @patch('cli.get_gmail_service')
    @patch('cli.get_gmail_watch_config')
    @patch.dict('os.environ', {'GOOGLE_CLOUD_PROJECT': 'test-project'})
    def test_watch_status(self, mock_get_config, mock_get_service):
        """Test Gmail watch status check."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        mock_config = Mock()
        mock_config.validate_topic_permissions.return_value = {
            'topic_exists': True,
            'gmail_has_publisher_role': True
        }
        mock_get_config.return_value = mock_config
        
        result = runner.invoke(app, [
            'watch', 'status', 'user123',
            '--topic', 'gmail-notifications'
        ])
        
        assert result.exit_code == 0
        assert 'Topic exists' in result.stdout
        assert 'Gmail has publisher permissions' in result.stdout


class TestMetricsCommands:
    """Test metrics CLI commands."""
    
    @patch('cli.get_metrics_collector')
    @patch('cli.get_db_session')
    @patch('cli.OCRQueryService')
    def test_metrics_dump_json(self, mock_ocr_service_class, mock_db_session, mock_get_collector):
        """Test metrics dump in JSON format."""
        # Mock metrics collector
        mock_collector = Mock()
        mock_collector.get_system_metrics.return_value = {
            'total_requests': 100,
            'overall_success_rate': 95.0
        }
        mock_collector.get_ocr_metrics.return_value = {
            'azure': {'requests': 50, 'success_rate': 96.0}
        }
        mock_get_collector.return_value = mock_collector
        
        # Mock OCR query service
        mock_ocr_service = Mock()
        mock_ocr_service.get_ocr_performance_stats.return_value = {
            'total_runs': 100,
            'avg_confidence': 85.5
        }
        mock_ocr_service_class.return_value = mock_ocr_service
        
        # Mock database session
        mock_db = Mock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        result = runner.invoke(app, ['metrics', 'dump', '--format', 'json'])
        
        assert result.exit_code == 0
        assert 'Metrics dump saved to' in result.stdout
    
    @patch('cli.get_metrics_collector')
    def test_metrics_dump_csv(self, mock_get_collector):
        """Test metrics dump in CSV format."""
        mock_collector = Mock()
        mock_collector.get_system_metrics.return_value = {
            'total_requests': 100,
            'overall_success_rate': 95.0
        }
        mock_collector.get_ocr_metrics.return_value = {
            'azure': {'requests': 50, 'success_rate': 96.0}
        }
        mock_get_collector.return_value = mock_collector
        
        result = runner.invoke(app, [
            'metrics', 'dump', '--format', 'csv',
            '--no-database'  # Skip database metrics for simplicity
        ])
        
        assert result.exit_code == 0
        assert 'Metrics dump saved to' in result.stdout
    
    def test_metrics_dump_invalid_format(self):
        """Test metrics dump with invalid format."""
        result = runner.invoke(app, ['metrics', 'dump', '--format', 'xml'])
        
        assert result.exit_code == 1
        assert "format must be 'json', 'csv', or 'yaml'" in result.stdout
    
    @patch('cli.get_metrics_collector')
    def test_metrics_summary(self, mock_get_collector):
        """Test metrics summary command."""
        mock_collector = Mock()
        mock_collector.get_system_metrics.return_value = {
            'total_requests': 100,
            'overall_success_rate': 95.0,
            'total_cost_cents': 150,
            'engines_count': 3,
            'last_updated': '2024-01-01T00:00:00'
        }
        mock_collector.get_ocr_metrics.return_value = {
            'azure': {
                'requests': 50,
                'success_rate': 96.0,
                'avg_latency_ms': 250
            },
            'google': {
                'requests': 30,
                'success_rate': 94.0,
                'avg_latency_ms': 300
            }
        }
        mock_get_collector.return_value = mock_collector
        
        result = runner.invoke(app, ['metrics', 'summary'])
        
        assert result.exit_code == 0
        assert 'System Metrics Summary' in result.stdout
        assert 'Total Requests: 100' in result.stdout
        assert 'Success Rate: 95.0%' in result.stdout
        assert 'AZURE' in result.stdout
        assert 'GOOGLE' in result.stdout


class TestMainCLI:
    """Test main CLI functionality."""
    
    def test_admin_help(self):
        """Test admin help command."""
        result = runner.invoke(app, ['admin-help'])
        
        assert result.exit_code == 0
        assert 'Gmail Label Management' in result.stdout
        assert 'Gmail Watch (Push Notifications)' in result.stdout
        assert 'System Metrics' in result.stdout
        assert 'labels list USER_ID' in result.stdout
    
    def test_main_help(self):
        """Test main CLI help."""
        result = runner.invoke(app, ['--help'])
        
        assert result.exit_code == 0
        assert 'labels' in result.stdout
        assert 'watch' in result.stdout
        assert 'metrics' in result.stdout
    
    def test_labels_subcommand_help(self):
        """Test labels subcommand help."""
        result = runner.invoke(app, ['labels', '--help'])
        
        assert result.exit_code == 0
        assert 'Gmail label management commands' in result.stdout
        assert 'list' in result.stdout
        assert 'ensure' in result.stdout
        assert 'assign' in result.stdout
    
    def test_watch_subcommand_help(self):
        """Test watch subcommand help."""
        result = runner.invoke(app, ['watch', '--help'])
        
        assert result.exit_code == 0
        assert 'Gmail watch (push notifications) commands' in result.stdout
        assert 'start' in result.stdout
        assert 'stop' in result.stdout
        assert 'status' in result.stdout
    
    def test_metrics_subcommand_help(self):
        """Test metrics subcommand help."""
        result = runner.invoke(app, ['metrics', '--help'])
        
        assert result.exit_code == 0
        assert 'System metrics and reporting commands' in result.stdout
        assert 'dump' in result.stdout
        assert 'summary' in result.stdout


if __name__ == "__main__":
    # Run specific test categories
    import sys
    
    if len(sys.argv) > 1:
        test_class = sys.argv[1]
        if test_class == "labels":
            pytest.main(["-v", "test_admin_cli_commands.py::TestLabelsCommands"])
        elif test_class == "watch":
            pytest.main(["-v", "test_admin_cli_commands.py::TestWatchCommands"])
        elif test_class == "metrics":
            pytest.main(["-v", "test_admin_cli_commands.py::TestMetricsCommands"])
        elif test_class == "main":
            pytest.main(["-v", "test_admin_cli_commands.py::TestMainCLI"])
        else:
            print("Available test categories: labels, watch, metrics, main")
    else:
        # Run all tests
        pytest.main(["-v", "test_admin_cli_commands.py"])
