import json
import torch
import argparse
import numpy as np
import pickle

from tqdm import tqdm
from fairseq.models.bart import BARTModel
from utils import get_cmlm_probability


def read_lines(file_path):
    files = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            files.append(line.strip())
    return files


def main(args):
    # read data (source, target and extracted entities)
    xsum_source = read_lines(args.source_path)
    xsum_target = read_lines(args.target_path)
    xsum_ents = json.load(open(args.ent_path, 'r'))
    
    assert len(xsum_source) == len(xsum_target) == len(xsum_ents)
    print('- load {} samples.'.format(len(xsum_source)))
    
    # load BART model
    finetuned_bart = BARTModel.from_pretrained(args.bart_path,
                                               checkpoint_file=args.checkpoint_file,
                                               data_name_or_path=args.data_name_or_path)
    finetuned_bart.cuda()
    finetuned_bart.eval()
    finetuned_bart.half()
    print('- fine-tuned bart model loaded.')
    
    def get_posterior(source, target, ents):
        """Get the weight of target sample.
        """
        if len(ents) == 0:
            return [1.0]

        posteriors = []
        for e in ents:
            entity = target[e['start']: e['end']]
            assert entity in target
            masked_hypothesis = '<s> ' + target[0: e['start']] + '###' + target[e['end']:]

            masked_input = masked_hypothesis + ' <\s> ' + source
            with torch.no_grad():
                posterior = get_cmlm_probability(finetuned_bart,
                                                 '<s> ' + target,
                                                 masked_input,
                                                 (e['start'] + 4, e['end'] + 4),
                                                 entity, verbose=False)
            posteriors.append(posterior)

        assert len(posteriors) == len(ents)
        return posteriors
    
    posteriors = []
    for i, (source, target, ents) in tqdm(enumerate(zip(xsum_source, xsum_target, xsum_ents))):
        if i == 0:
            print('- first output: {}'.format(get_posterior(source, target, ents['ents'])))
        posteriors.append(get_posterior(source, target, ents['ents']))
    
    # save posterior values to file
    with open("posteriors.pkl", "wb") as fp:
        pickle.dump(posteriors, fp)


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()

    PARSER.add_argument("--source_path", type=str, help="source file path.")
    PARSER.add_argument("--target_path", type=str, help="target file path.")
    PARSER.add_argument("--ent_path", type=str, help="extracted entities path.")
    PARSER.add_argument("--bart_path", type=str, help="BART model path.")
    PARSER.add_argument("--checkpoint_file", type=str, default='checkpoint_best.pt', help="checkpoint file name.")
    PARSER.add_argument("--data_name_or_path", type=str, help="BART data bin file.")

    ARGS = PARSER.parse_args()
    main(ARGS)