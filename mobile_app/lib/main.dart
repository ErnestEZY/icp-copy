import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
// Import for Android features.
import 'package:webview_flutter_android/webview_flutter_android.dart';
// Import for iOS features.
import 'package:webview_flutter_wkwebview/webview_flutter_wkwebview.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'dart:convert';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final bool isMobile =
        Theme.of(context).platform == TargetPlatform.android ||
        Theme.of(context).platform == TargetPlatform.iOS;

    return MaterialApp(
      title: 'Interview Coach Prep',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF007BFF)),
        useMaterial3: true,
      ),
      home: isMobile ? const WebViewPage() : const WindowsFallbackPage(),
    );
  }
}

class WindowsFallbackPage extends StatelessWidget {
  const WindowsFallbackPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Interview Coach Prep')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.computer, size: 64, color: Colors.blue),
            const SizedBox(height: 16),
            const Text(
              'Windows Preview',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 32.0),
              child: Text(
                'The mobile app WebView is optimized for Android and iOS. To preview the site on Windows, please use your browser.',
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open in Browser'),
              onPressed: () async {
                final Uri url = Uri.parse(
                  'https://interview-coach-prep.onrender.com/',
                );
                if (!await launchUrl(
                  url,
                  mode: LaunchMode.externalApplication,
                )) {
                  debugPrint('Could not launch $url');
                }
              },
            ),
            const SizedBox(height: 12),
            const Text(
              'Note: Run on an Android Emulator or Physical Device for the full app experience.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class WebViewPage extends StatefulWidget {
  const WebViewPage({super.key});

  @override
  State<WebViewPage> createState() => _WebViewPageState();
}

class _WebViewPageState extends State<WebViewPage> {
  late final WebViewController _controller;
  bool _isLoading = true;
  final FlutterTts _flutterTts = FlutterTts();

  Future<void> _requestPermissions() async {
    // Request microphone and storage permissions
    Map<Permission, PermissionStatus> statuses = await [
      Permission.microphone,
      Permission.storage,
      // For Android 13+ storage permissions are different, but permission_handler handles it
      Permission.photos,
      Permission.videos,
      Permission.audio,
      Permission.camera,
    ].request();

    debugPrint('Permission statuses: $statuses');
  }

  @override
  void initState() {
    super.initState();
    _requestPermissions();

    // #docregion platform_features
    late final PlatformWebViewControllerCreationParams params;
    if (WebViewPlatform.instance is WebKitWebViewPlatform) {
      params = WebKitWebViewControllerCreationParams(
        allowsInlineMediaPlayback: true,
      );
    } else {
      params = const PlatformWebViewControllerCreationParams();
    }

    final WebViewController controller =
        WebViewController.fromPlatformCreationParams(params);
    // #enddocregion platform_features

    controller
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setUserAgent(
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
      )
      ..setBackgroundColor(const Color(0x00000000))
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            debugPrint('WebView is loading (progress : $progress%)');
          },
          onPageStarted: (String url) {
            debugPrint('Page started loading: $url');
            setState(() {
              _isLoading = true;
            });
          },
          onPageFinished: (String url) {
            debugPrint('Page finished loading: $url');
            setState(() {
              _isLoading = false;
            });
            // If user navigates to the interview page, ensure permissions are requested
            if (url.contains('interview')) {
              _requestPermissions();
            }
          },
          onWebResourceError: (WebResourceError error) {
            debugPrint('''
Page resource error:
  code: ${error.errorCode}
  description: ${error.description}
  errorType: ${error.errorType}
  isForMainFrame: ${error.isForMainFrame}
          ''');
          },
          onNavigationRequest: (NavigationRequest request) {
            return NavigationDecision.navigate;
          },
        ),
      )
      ..addJavaScriptChannel(
        'PermissionHandler',
        onMessageReceived: (JavaScriptMessage message) async {
          final String permissionType = message.message;
          if (permissionType == 'camera') {
            await Permission.camera.request();
          } else if (permissionType == 'microphone') {
            await Permission.microphone.request();
          }
          // Refresh permissions after request
          _requestPermissions();
        },
      )
      ..addJavaScriptChannel(
        'Toaster',
        onMessageReceived: (JavaScriptMessage message) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(message.message)));
        },
      )
      ..addJavaScriptChannel(
        'TTSHandler',
        onMessageReceived: (JavaScriptMessage message) async {
          try {
            final Map<String, dynamic> data = jsonDecode(message.message);
            final String text = data['text'] ?? '';
            final String gender = data['gender'] ?? 'female';

            if (text.isNotEmpty) {
              await _flutterTts.setLanguage("en-US");
              await _flutterTts.setPitch(1.0);
              await _flutterTts.setSpeechRate(0.5); // Normal speed

              if (gender == 'male') {
                // Try to find a male voice, otherwise use default
                await _flutterTts.setVoice({
                  "name": "en-us-x-iol-local",
                  "locale": "en-US",
                });
              } else {
                await _flutterTts.setVoice({
                  "name": "en-us-x-sfg-local",
                  "locale": "en-US",
                });
              }

              await _flutterTts.speak(text);
            }
          } catch (e) {
            debugPrint('TTS Error: $e');
          }
        },
      )
      ..loadRequest(Uri.parse('https://interview-coach-prep.onrender.com/'));

    // #docregion platform_features
    if (controller.platform is AndroidWebViewController) {
      AndroidWebViewController.enableDebugging(true);
      final androidController = controller.platform as AndroidWebViewController;

      androidController.setMediaPlaybackRequiresUserGesture(false);

      // Enable mixed content mode for loading various resources
      // WebSettings.MIXED_CONTENT_ALWAYS_ALLOW = 0
      // In webview_flutter_android, we can't access WebSettings constants directly easily,
      // but we can try to find if there's a method for it.
      // Actually, the current webview_flutter_android version might not expose it directly
      // without using platform-specific code.
      // However, setMediaPlaybackRequiresUserGesture is the most important one.

      // These settings help with Speech Synthesis and overall web performance
      // Although setDomStorageEnabled was missing, we can ensure mixed content is allowed
      // which is often required for loading resources in some environments
      // We also ensure debugging is on for development
      AndroidWebViewController.enableDebugging(true);

      // This is the correct method for webview_flutter_android 4.10.11+
      (controller.platform as AndroidWebViewController)
          .setOnPlatformPermissionRequest((request) async {
            // Explicitly grant all requested resources (audio, video, etc.)
            await request.grant();
          });

      (controller.platform as AndroidWebViewController).setOnShowFileSelector((
        FileSelectorParams params,
      ) async {
        final result = await FilePicker.platform.pickFiles();

        if (result != null && result.files.single.path != null) {
          final String path = result.files.single.path!;
          return [Uri.file(path).toString()];
        }
        return [];
      });
    }
    // #enddocregion platform_features

    _controller = controller;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (bool didPop, Object? result) async {
        if (didPop) return;

        if (await _controller.canGoBack()) {
          await _controller.goBack();
        } else {
          // If the WebView cannot go back, we allow the app to pop/exit
          if (context.mounted) {
            // We set canPop to true temporarily or manually pop
            // Since we are in a PopScope with canPop: false, we need to handle the exit
            final NavigatorState navigator = Navigator.of(context);
            if (navigator.canPop()) {
              navigator.pop();
            } else {
              // If there's no more routes to pop, it's the home screen,
              // we can close the app or just do nothing (standard behavior)
            }
          }
        }
      },
      child: Scaffold(
        backgroundColor: Colors.white,
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_isLoading) const Center(child: CircularProgressIndicator()),
            ],
          ),
        ),
      ),
    );
  }
}
