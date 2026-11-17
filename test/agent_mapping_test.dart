import 'package:airtrain/agent_link.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('parseAgentUri', () {
    test('accepts the URL printed by airtrain serve', () {
      final u = parseAgentUri('ws://192.168.1.20:8765/?token=abc123');
      expect(u.toString(), 'ws://192.168.1.20:8765/?token=abc123');
    });
    test('host only plus token field', () {
      expect(parseAgentUri('192.168.1.20', 'tok').toString(), 'ws://192.168.1.20:8765/?token=tok');
    });
    test('token field overrides URL token', () {
      expect(parseAgentUri('ws://10.0.0.5:9000/?token=old', 'new').queryParameters['token'], 'new');
    });
    test('missing token is rejected', () {
      expect(() => parseAgentUri('10.0.0.5:8765'), throwsFormatException);
    });
  });
}
