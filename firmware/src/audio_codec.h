#ifndef INKSIGHT_AUDIO_CODEC_H
#define INKSIGHT_AUDIO_CODEC_H

#include <Arduino.h>
#include <stdint.h>

#define CODEC_SAMPLE_RATE   16000
#define CODEC_BUFFER_SIZE   1024

class AudioCodec {
public:
    virtual ~AudioCodec() = default;

    virtual bool Start() = 0;
    virtual void Stop() = 0;
    virtual void EnableInput(bool enable) = 0;
    virtual void EnableOutput(bool enable) = 0;

    virtual int Read(int16_t* dest, int maxSamples) = 0;
    virtual int Write(const int16_t* data, int samples) = 0;
    virtual void FlushOutput() = 0;

    bool inputEnabled() const { return input_enabled_; }
    bool outputEnabled() const { return output_enabled_; }
    bool isDuplex() const { return duplex_; }
    int inputSampleRate() const { return CODEC_SAMPLE_RATE; }
    int outputSampleRate() const { return CODEC_SAMPLE_RATE; }

protected:
    bool duplex_ = false;
    bool input_enabled_ = false;
    bool output_enabled_ = false;
};

class Inmp441Max98357Codec : public AudioCodec {
public:
    explicit Inmp441Max98357Codec(bool duplex);
    ~Inmp441Max98357Codec() override;

    bool Start() override;
    void Stop() override;
    void EnableInput(bool enable) override;
    void EnableOutput(bool enable) override;
    int Read(int16_t* dest, int maxSamples) override;
    int Write(const int16_t* data, int samples) override;
    void FlushOutput() override;

private:
    bool started_ = false;
    int32_t read_buf_[CODEC_BUFFER_SIZE];
    int16_t stereo_buf_[CODEC_BUFFER_SIZE * 2];
};

#endif
