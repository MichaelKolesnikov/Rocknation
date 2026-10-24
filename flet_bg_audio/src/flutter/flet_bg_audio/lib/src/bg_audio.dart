import 'dart:async';

import 'package:audio_service/audio_service.dart';
import 'package:audio_session/audio_session.dart';
import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

/// Audio handler that lives in the Android foreground service.
///
/// The whole playlist is handed to just_audio, so track transitions keep
/// working while the screen is off and Python is not involved.
class _PlayerHandler extends BaseAudioHandler with QueueHandler, SeekHandler {
  final AudioPlayer player = AudioPlayer();

  _PlayerHandler() {
    player.playbackEventStream.listen(_broadcastState,
        onError: (Object e, StackTrace st) {
      debugPrint("BgAudio playback error: $e");
    });
    player.currentIndexStream.listen((index) {
      final items = queue.value;
      if (index != null && index < items.length) {
        mediaItem.add(items[index]);
      }
    });
    player.durationStream.listen((duration) {
      final index = player.currentIndex;
      final items = queue.value;
      if (index == null || duration == null || index >= items.length) {
        return;
      }
      final item = items[index].copyWith(duration: duration);
      items[index] = item;
      mediaItem.add(item);
    });
  }

  Future<void> setTracks(List<MediaItem> items, int index) async {
    queue.add(items);
    if (index < items.length) {
      mediaItem.add(items[index]);
    }
    await player.setAudioSources(
      items.map(_toSource).toList(),
      initialIndex: index,
      initialPosition: Duration.zero,
    );
  }

  AudioSource _toSource(MediaItem item) {
    final url = item.extras!["url"] as String;
    if (url.startsWith("/")) {
      return AudioSource.file(url, tag: item);
    }
    return AudioSource.uri(Uri.parse(url), tag: item);
  }

  @override
  Future<void> play() => player.play();

  @override
  Future<void> pause() => player.pause();

  @override
  Future<void> stop() async {
    await player.stop();
    await super.stop();
  }

  @override
  Future<void> seek(Duration position) => player.seek(position);

  @override
  Future<void> skipToNext() => player.seekToNext();

  @override
  Future<void> skipToPrevious() async {
    // Like most players: restart the track unless we are at its very start.
    if (player.position > const Duration(seconds: 3) ||
        !player.hasPrevious) {
      await player.seek(Duration.zero);
    } else {
      await player.seekToPrevious();
    }
  }

  @override
  Future<void> skipToQueueItem(int index) =>
      player.seek(Duration.zero, index: index);

  @override
  Future<void> setShuffleMode(AudioServiceShuffleMode shuffleMode) async {
    final enabled = shuffleMode != AudioServiceShuffleMode.none;
    if (enabled) {
      await player.shuffle();
    }
    await player.setShuffleModeEnabled(enabled);
    playbackState.add(playbackState.value.copyWith(shuffleMode: shuffleMode));
  }

  @override
  Future<void> setRepeatMode(AudioServiceRepeatMode repeatMode) async {
    await player.setLoopMode(switch (repeatMode) {
      AudioServiceRepeatMode.one => LoopMode.one,
      AudioServiceRepeatMode.all || AudioServiceRepeatMode.group => LoopMode.all,
      AudioServiceRepeatMode.none => LoopMode.off,
    });
    playbackState.add(playbackState.value.copyWith(repeatMode: repeatMode));
  }

  void _broadcastState(PlaybackEvent event) {
    final playing = player.playing;
    playbackState.add(playbackState.value.copyWith(
      controls: [
        MediaControl.skipToPrevious,
        if (playing) MediaControl.pause else MediaControl.play,
        MediaControl.skipToNext,
        MediaControl.stop,
      ],
      systemActions: const {
        MediaAction.seek,
        MediaAction.seekForward,
        MediaAction.seekBackward,
      },
      androidCompactActionIndices: const [0, 1, 2],
      processingState: const {
        ProcessingState.idle: AudioProcessingState.idle,
        ProcessingState.loading: AudioProcessingState.loading,
        ProcessingState.buffering: AudioProcessingState.buffering,
        ProcessingState.ready: AudioProcessingState.ready,
        ProcessingState.completed: AudioProcessingState.completed,
      }[player.processingState]!,
      playing: playing,
      updatePosition: player.position,
      bufferedPosition: player.bufferedPosition,
      speed: player.speed,
      queueIndex: event.currentIndex,
    ));
  }
}

class BgAudioService extends FletService {
  BgAudioService({required super.control});

  // AudioService.init() may be called only once per process, while Flet can
  // create the service several times (e.g. after a page reload).
  static Future<_PlayerHandler>? _handlerFuture;

  _PlayerHandler? _handler;
  final List<StreamSubscription> _subscriptions = [];
  Timer? _positionTimer;
  int _lastPositionMs = -1;

  @override
  void init() {
    super.init();
    debugPrint("BgAudio(${control.id}).init: ${control.properties}");
    control.addInvokeMethodListener(_invokeMethod);
    _handlerFuture ??= _createHandler();
    _handlerFuture!.then(_attach);
  }

  Future<_PlayerHandler> _createHandler() async {
    final session = await AudioSession.instance;
    await session.configure(const AudioSessionConfiguration.music());
    return AudioService.init(
      builder: () => _PlayerHandler(),
      config: AudioServiceConfig(
        androidNotificationChannelId: control.getString(
            "notification_channel_id", "flet.bg_audio.channel")!,
        androidNotificationChannelName:
            control.getString("notification_channel_name", "Music")!,
        androidNotificationIcon: control.getString(
            "notification_icon", "mipmap/ic_launcher")!,
        androidNotificationOngoing: true,
        androidStopForegroundOnPause: true,
      ),
    );
  }

  void _attach(_PlayerHandler handler) {
    _handler = handler;
    final player = handler.player;

    _subscriptions.add(player.playerStateStream.listen((state) {
      control.triggerEvent("state_change", {
        "playing": state.playing,
        "processing": state.processingState.name,
      });
    }));

    _subscriptions.add(player.currentIndexStream.listen((index) {
      if (index != null) {
        control.triggerEvent("track_change", {"index": index});
      }
    }));

    _subscriptions.add(player.playbackEventStream.listen((_) {},
        onError: (Object e, StackTrace st) {
      control.triggerEvent("error", {"message": e.toString()});
    }));

    _positionTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      final positionMs = player.position.inMilliseconds;
      if (positionMs == _lastPositionMs) {
        return;
      }
      _lastPositionMs = positionMs;
      control.triggerEvent("position_change", {
        "position": positionMs,
        "duration": player.duration?.inMilliseconds ?? 0,
      });
    });
  }

  Future<_PlayerHandler> get _ready async => _handler ?? await _handlerFuture!;

  MediaItem _parseTrack(dynamic t) {
    final art = t["art_uri"] as String?;
    return MediaItem(
      id: t["id"] as String,
      title: t["title"] as String? ?? "",
      artist: t["artist"] as String?,
      album: t["album"] as String?,
      artUri: art != null && art.isNotEmpty ? Uri.parse(art) : null,
      extras: {"url": t["url"] as String},
    );
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    debugPrint("BgAudio.$name($args)");
    final handler = await _ready;
    final player = handler.player;
    switch (name) {
      case "set_playlist":
        final tracks =
            (args["tracks"] as List).map(_parseTrack).toList(growable: true);
        final index = (args["index"] as num? ?? 0).toInt();
        final autoplay = args["autoplay"] as bool? ?? true;
        final shuffle = args["shuffle"] as bool? ?? false;
        // Loading a remote source can take a while; report the outcome via
        // events instead of keeping the Python call waiting.
        handler.setTracks(tracks, index).then((_) async {
          await handler.setShuffleMode(shuffle
              ? AudioServiceShuffleMode.all
              : AudioServiceShuffleMode.none);
          if (autoplay) {
            handler.play();
          }
        }).catchError((Object e) {
          control.triggerEvent("error", {"message": e.toString()});
        });
        break;
      case "play":
        handler.play();
        break;
      case "pause":
        await handler.pause();
        break;
      case "stop":
        await handler.stop();
        break;
      case "seek":
        await handler
            .seek(Duration(milliseconds: (args["position"] as num).toInt()));
        break;
      case "next":
        await handler.skipToNext();
        break;
      case "previous":
        await handler.skipToPrevious();
        break;
      case "skip_to":
        await handler.skipToQueueItem((args["index"] as num).toInt());
        break;
      case "set_shuffle":
        await handler.setShuffleMode(args["enabled"] == true
            ? AudioServiceShuffleMode.all
            : AudioServiceShuffleMode.none);
        break;
      case "set_repeat":
        await handler.setRepeatMode(switch (args["mode"] as String?) {
          "one" => AudioServiceRepeatMode.one,
          "all" => AudioServiceRepeatMode.all,
          _ => AudioServiceRepeatMode.none,
        });
        break;
      case "get_state":
        return {
          "index": player.currentIndex,
          "playing": player.playing,
          "processing": player.processingState.name,
          "position": player.position.inMilliseconds,
          "duration": player.duration?.inMilliseconds ?? 0,
          "queue_length": handler.queue.value.length,
        };
      default:
        throw Exception("Unknown BgAudio method: $name");
    }
    return null;
  }

  @override
  void dispose() {
    debugPrint("BgAudio(${control.id}).dispose()");
    control.removeInvokeMethodListener(_invokeMethod);
    _positionTimer?.cancel();
    for (final s in _subscriptions) {
      s.cancel();
    }
    // The handler and its player are intentionally kept alive: they belong
    // to the foreground service, not to this Flet control.
    super.dispose();
  }
}
