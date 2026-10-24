import 'package:flet/flet.dart';

import 'bg_audio.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "BgAudio":
        return BgAudioService(control: control);
      default:
        return null;
    }
  }
}
