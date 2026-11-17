import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

/// Connection state of one paired PC agent.
enum LinkStatus { connecting, connected, unauthorized, error }

/// Builds the agent WebSocket URI from what the user typed.
///
/// Accepts a full `ws://host:port/?token=...` URL (as printed by `airtrain serve`),
/// or just `host`, `host:port`. A non-empty [token] overrides the one in the URL.
Uri parseAgentUri(String input, [String token = '']) {
  var s = input.trim();
  if (s.isEmpty) throw const FormatException('Enter the agent address');
  if (!s.contains('://')) s = 'ws://$s';
  var u = Uri.parse(s);
  if (u.scheme != 'ws' && u.scheme != 'wss') throw const FormatException('Use a ws:// address');
  if (u.host.isEmpty) throw const FormatException('Missing host');
  final t = token.trim().isNotEmpty ? token.trim() : (u.queryParameters['token'] ?? '');
  if (t.isEmpty) throw const FormatException('Missing pairing token');
  return Uri(scheme: u.scheme, host: u.host, port: u.hasPort ? u.port : 8765, path: '/', queryParameters: {'token': t});
}

/// One live WebSocket link to an `airtrain serve` agent, with automatic reconnect.
class AgentLink {
  AgentLink(this.uri, {required this.onMessage, required this.onStatus});

  final Uri uri;
  final void Function(Map<String, dynamic> msg) onMessage;
  final void Function(LinkStatus status, String? error) onStatus;

  WebSocketChannel? _ch;
  StreamSubscription<dynamic>? _sub;
  Timer? _retry;
  bool _closed = false;

  String get id => '${uri.host}:${uri.port}';
  String get address => id;

  Future<void> connect() async {
    if (_closed) return;
    onStatus(LinkStatus.connecting, null);
    try {
      final ch = WebSocketChannel.connect(uri);
      _ch = ch;
      await ch.ready.timeout(const Duration(seconds: 6));
      onStatus(LinkStatus.connected, null);
      _sub = ch.stream.listen(
        (raw) {
          try {
            final m = jsonDecode(raw as String);
            if (m is Map<String, dynamic>) onMessage(m);
          } catch (_) {}
        },
        onDone: () => _scheduleRetry(null),
        onError: (Object e) => _scheduleRetry(e),
        cancelOnError: true,
      );
    } catch (e) {
      _scheduleRetry(e);
    }
  }

  void _scheduleRetry(Object? e) {
    _sub?.cancel();
    _sub = null;
    _ch = null;
    if (_closed) return;
    final msg = e?.toString() ?? 'Disconnected';
    onStatus(msg.contains('401') ? LinkStatus.unauthorized : LinkStatus.error, msg);
    _retry?.cancel();
    _retry = Timer(const Duration(seconds: 3), connect);
  }

  /// Sends a command such as `pause` or `resume`.
  void send(String cmd) => _ch?.sink.add(jsonEncode({'cmd': cmd}));

  void close() {
    _closed = true;
    _retry?.cancel();
    _sub?.cancel();
    _ch?.sink.close();
  }
}
