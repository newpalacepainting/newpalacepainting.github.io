import "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js";
import baguetteBox from "https://cdnjs.cloudflare.com/ajax/libs/baguettebox.js/1.11.1/baguetteBox.min.js";

window.addEventListener('load', function() {
  if (typeof baguetteBox !== 'undefined') {
    baguetteBox.run('.baguette-gallery');
  }
});
